from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from ..models import Document, Signature
from ..forms import DirectorDecisionForm
from ..utils import transition_document, notify_status_change, verify_document_integrity
from .. import crypto_utils


def is_director(user):
    return hasattr(user, "profile") and user.profile.role == "director"


@login_required
@user_passes_test(is_director)
def dashboard(request):
    pending = Document.objects.filter(status="awaiting_director")
    approved = Document.objects.filter(status="approved")
    returned = Document.objects.filter(status="under_dept_review", director_remarks__isnull=False)
    week_ago = timezone.now() - timedelta(days=7)
    weekly_approved = Document.objects.filter(status="approved", created_at__gte=week_ago).count()
    weekly_returned = Document.objects.filter(status="under_dept_review", director_remarks__isnull=False, created_at__gte=week_ago).count()
    recent_sigs = Signature.objects.filter(user=request.user).order_by("-signed_at")[:5]
    return render(request, "director/dashboard.html", {
        "pending": pending[:5],
        "approved": approved[:5],
        "returned": returned[:5],
        "pending_count": pending.count(),
        "approved_count": approved.count(),
        "returned_count": returned.count(),
        "weekly_approved": weekly_approved,
        "weekly_returned": weekly_returned,
        "recent_sigs": recent_sigs,
    })


@login_required
@user_passes_test(is_director)
def all_pending(request):
    qs = Document.objects.filter(status="awaiting_director").order_by("-created_at")
    page = request.GET.get("page", 1)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)
    return render(request, "director/all_pending.html", {"page_obj": page_obj})


@login_required
@user_passes_test(is_director)
def document_detail(request, pk):
    doc = get_object_or_404(Document, pk=pk, status="awaiting_director")

    external_check = None
    if request.method == "POST":
        form = DirectorDecisionForm(request.POST, request.FILES)
        if form.is_valid():
            decision = form.cleaned_data["decision"]
            remarks = form.cleaned_data["remarks"]

            external_file = request.FILES.get("external_signed_file")
            if external_file:
                from django.core.files.base import ContentFile
                import hashlib
                file_bytes = external_file.read()
                ext_hash = hashlib.sha256(file_bytes).hexdigest()
                external_file.seek(0)

                if doc.document_hash and doc.digital_signatures.exists():
                    if ext_hash == doc.document_hash:
                        valid, msg = verify_document_integrity(doc)
                        external_check = {"match": True, "valid": valid, "msg": msg}
                    else:
                        external_check = {
                            "match": False,
                            "doc_hash": doc.document_hash[:16] + "...",
                            "ext_hash": ext_hash[:16] + "...",
                            "msg": "File hash does not match the system record. This PDF was not signed by our system or has been modified."
                        }
                else:
                    external_check = {"match": False, "msg": "Document has no digital signature on record. Cannot cross-check."}

                doc.external_signed_file.save(f"external_{doc.document_id}.pdf", ContentFile(file_bytes), save=True)

            sig = Signature.objects.create(
                document=doc,
                user=request.user,
                role="Director",
                signature_image=request.FILES.get("signature", ""),
                remarks=remarks,
            )

            stamp_file = request.FILES.get("stamp")
            if stamp_file:
                doc.municipal_stamp = stamp_file

            if decision == "approve":
                transition_document(doc, "approved", request.user, remarks or "Document approved by Director")
                doc.director_approval = True
                doc.director_remarks = remarks
                doc.director_signed_at = timezone.now()
                doc.current_holder = "Approved - Returning to Registry"
                doc.save()
                transition_document(doc, "returned_to_registry", request.user, "Approved document returned to Registry")
                doc.current_holder = "Registry Office"
                doc.save()
                notify_status_change(doc)
                messages.success(request, "Document approved and returned to Registry.")
            else:
                transition_document(doc, "under_dept_review", request.user, remarks or "Returned for correction by Director")
                doc.current_holder = f"{doc.department.name} Office (Returned for Correction)"
                doc.save()
                notify_status_change(doc)
                messages.info(request, "Document returned to department for correction.")

            return redirect("director_dashboard")
    else:
        form = DirectorDecisionForm()
    return render(request, "director/document_detail.html", {"doc": doc, "form": form, "external_check": external_check})
