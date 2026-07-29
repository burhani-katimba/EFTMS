import io
import json
import hashlib
from datetime import datetime
from pathlib import Path

import qrcode
from django.core.files.base import ContentFile
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import Notification, DocumentLog, Document, DigitalSignature
from . import crypto_utils


def generate_qr_code(document):
    verify_url = f"{settings.BASE_URL}/verify/{document.document_id}/"
    payload = {
        "id": document.document_id,
        "h": (document.document_hash or "")[:16],
        "v": verify_url,
    }
    data_str = json.dumps(payload, separators=(",", ":"))
    qr = qrcode.QRCode(box_size=10, border=4, error_correction=qrcode.constants.ERROR_CORRECT_Q)
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    filename = f"{document.document_id}.png"
    document.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
    return document.qr_code


def sign_and_stamp_document(document, user):
    if not document.uploaded_file:
        return None
    file_path = document.uploaded_file.path
    if not Path(file_path).exists():
        return None

    doc_hash = crypto_utils.compute_file_hash(file_path)
    signature_hex = crypto_utils.sign_hash(doc_hash)
    pub_key_pem = crypto_utils.get_public_key_pem()
    cert_fingerprint = hashlib.sha256(pub_key_pem.encode()).hexdigest()

    document.document_hash = doc_hash
    document.save(update_fields=["document_hash"])

    DigitalSignature.objects.create(
        document=document,
        document_hash=doc_hash,
        signature_value=signature_hex,
        signed_by=user,
        certificate_fingerprint=cert_fingerprint,
    )

    _stamp_pdf(document, user)


def _stamp_pdf(document, user):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    file_path = document.uploaded_file.path
    if not Path(file_path).exists():
        return

    reader = PdfReader(file_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    qr_path = document.qr_code.path if document.qr_code else None
    overlay = io.BytesIO()
    c = canvas.Canvas(overlay, pagesize=letter)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 760, "MUNICIPAL CERTIFIED DOCUMENT")
    c.setFont("Helvetica", 8)
    c.drawString(40, 745, f"ID: {document.document_id}")
    c.drawString(40, 730, f"Status: {document.get_status_display()}")
    c.drawString(40, 715, f"SHA-256: {document.document_hash[:32]}...")
    try:
        ds = document.digital_signatures.first()
        if ds:
            signer = ds.signed_by.get_full_name() or ds.signed_by.username
            c.drawString(40, 700, f"Signed: {signer} @ {ds.signed_at.strftime('%Y-%m-%d %H:%M')}")
    except Exception:
        pass
    if qr_path and Path(qr_path).exists():
        c.drawImage(qr_path, 440, 660, width=130, height=130)
    c.setFont("Helvetica", 6)
    c.drawString(40, 40, "This is a computer-generated certified copy. Verify at " + settings.BASE_URL + "/verify/" + document.document_id + "/")
    c.save()
    overlay.seek(0)
    overlay_pdf = PdfReader(overlay)
    writer.add_page(overlay_pdf.pages[0])

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    filename = f"certified_{document.document_id}.pdf"
    document.certified_file.save(filename, ContentFile(out.getvalue()), save=False)
    document.save(update_fields=["certified_file"])


def verify_document_integrity(document):
    ds = document.digital_signatures.first()
    if not ds:
        return False, "No digital signature record found."
    if not document.document_hash:
        return False, "No document hash recorded."

    current_hash = None
    if document.uploaded_file and Path(document.uploaded_file.path).exists():
        current_hash = crypto_utils.compute_file_hash(document.uploaded_file.path)

    if current_hash and current_hash != document.document_hash:
        return False, "Document file has been modified since signing."
    if current_hash is None and document.certified_file and Path(document.certified_file.path).exists():
        current_hash = crypto_utils.compute_file_hash(document.certified_file.path)

    valid = crypto_utils.verify_signature(document.document_hash, ds.signature_value)
    if valid:
        document.integrity_verified_at = datetime.now()
        document.save(update_fields=["integrity_verified_at"])
        ds.verified = True
        ds.verified_at = datetime.now()
        ds.save(update_fields=["verified", "verified_at"])
        return True, "Document integrity verified. Digital signature is valid."
    else:
        ds.verified = False
        ds.verified_at = datetime.now()
        ds.save(update_fields=["verified", "verified_at"])
        return False, "Digital signature verification failed."


def transition_document(document, to_status, user, comment=""):
    from_status = document.transition_to(to_status)
    DocumentLog.objects.create(
        document=document,
        from_status=from_status,
        to_status=to_status,
        changed_by=user,
        comment=comment,
    )
    return from_status


def send_email_notification(document, subject, message, email=None):
    email = email or document.applicant_email
    if not email:
        return None
    recipient_user = document.submitted_by if document.submitted_by and document.submitted_by.email == email else None
    notif = Notification.objects.create(
        document=document,
        recipient=recipient_user,
        recipient_email=email,
        recipient_phone=document.applicant_phone,
        subject=subject,
        message=message,
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
        notif.is_sent = True
        notif.sent_at = datetime.now()
        notif.save()
    except Exception:
        pass
    return notif


def notify_status_change(document):
    status_labels = dict(Document.STATUS_CHOICES)
    label = status_labels.get(document.status, document.status)
    subject = f"Document {document.document_id} - {label}"
    message = (
        f"Dear {document.applicant_name},\n\n"
        f"Your document '{document.title}' (ID: {document.document_id}) "
        f"has been updated to: {label}.\n\n"
        f"Current holder: {document.current_holder or 'N/A'}\n\n"
        f"Track your document: {settings.BASE_URL}/track/{document.document_id}/\n\n"
        f"Thank you."
    )
    return send_email_notification(document, subject, message)
