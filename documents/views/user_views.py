from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from ..models import Document, DocumentLog, Notification
from ..forms import DocumentSoftcopyForm
from ..utils import generate_qr_code, sign_and_stamp_document, notify_status_change


@login_required
def dashboard(request):
    docs = Document.objects.filter(submitted_by=request.user)
    documents = docs.order_by("-created_at")
    needs_action = docs.filter(status__in=["submitted", "returned_to_registry"])
    ready_docs = docs.filter(status="ready_for_collection")
    completed = docs.filter(status="collected")
    notifs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:5]
    return render(request, "user_docs/dashboard.html", {
        "documents": documents,
        "needs_action": needs_action,
        "ready_count": ready_docs.count(),
        "completed_count": completed.count(),
        "action_count": needs_action.count(),
        "notifications_list": notifs,
    })


@login_required
def submit_document(request):
    if request.method == "POST":
        form = DocumentSoftcopyForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.submitted_by = request.user
            doc.submitted_at = timezone.now()
            doc.applicant_name = request.user.get_full_name() or request.user.username
            doc.applicant_email = request.user.email
            doc.applicant_phone = request.user.profile.phone if hasattr(request.user, "profile") else ""
            doc.submission_type = "softcopy"
            doc.current_holder = "Pending Registry Review"
            doc.save()
            generate_qr_code(doc)
            sign_and_stamp_document(doc, request.user)
            DocumentLog.objects.create(
                document=doc, from_status="", to_status="submitted",
                changed_by=request.user, comment="Document submitted online",
            )
            notify_status_change(doc)
            messages.success(request, f"Document {doc.document_id} submitted successfully. Awaiting registry review.")
            return redirect("user_dashboard")
    else:
        form = DocumentSoftcopyForm()
    return render(request, "user_docs/submit_form.html", {"form": form})


@login_required
def track_document(request, pk):
    doc = get_object_or_404(Document, pk=pk, submitted_by=request.user)
    return render(request, "user_docs/track.html", {"doc": doc})


@login_required
def notifications_view(request):
    docs = Document.objects.filter(submitted_by=request.user)
    notifs = []
    for d in docs:
        for n in d.notifications.all():
            notifs.append(n)
    notifs.sort(key=lambda x: x.created_at, reverse=True)
    return render(request, "user_docs/notifications.html", {"notifications": notifs})


def public_track(request, document_id):
    doc = get_object_or_404(Document, document_id=document_id)
    return render(request, "user_docs/track.html", {"doc": doc})
