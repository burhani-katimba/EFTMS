from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from ..models import Document, DocumentComment, DocumentLog, Signature
from ..utils import transition_document, notify_status_change


def is_dept_officer(user):
    return hasattr(user, "profile") and user.profile.role == "department"


@login_required
@user_passes_test(is_dept_officer)
def dashboard(request):
    dept = request.user.profile.department
    pending = Document.objects.filter(department=dept, status="forwarded_to_dept")
    reviewing = Document.objects.filter(department=dept, status="under_dept_review")
    completed = Document.objects.filter(department=dept, status="awaiting_director")
    cutoff = timezone.now() - timedelta(hours=48)
    aging = pending.filter(created_at__lt=cutoff)
    recent_logs = DocumentLog.objects.filter(document__department=dept).select_related("document", "changed_by").order_by("-created_at")[:5]
    return render(request, "department/dashboard.html", {
        "pending": pending[:5],
        "reviewing": reviewing[:5],
        "completed": completed[:5],
        "pending_count": pending.count(),
        "reviewing_count": reviewing.count(),
        "completed_count": completed.count(),
        "aging_count": aging.count(),
        "recent_logs": recent_logs,
        "cutoff": cutoff,
    })


@login_required
@user_passes_test(is_dept_officer)
def pending_list(request):
    dept = request.user.profile.department
    qs = Document.objects.filter(department=dept, status="forwarded_to_dept").order_by("-created_at")
    page = request.GET.get("page", 1)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)
    return render(request, "department/pending_list.html", {"page_obj": page_obj})


@login_required
@user_passes_test(is_dept_officer)
def reviewing_list(request):
    dept = request.user.profile.department
    qs = Document.objects.filter(department=dept, status="under_dept_review").order_by("-created_at")
    page = request.GET.get("page", 1)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)
    return render(request, "department/reviewing_list.html", {"page_obj": page_obj})


@login_required
@user_passes_test(is_dept_officer)
def document_detail(request, pk):
    dept = request.user.profile.department
    doc = get_object_or_404(Document, pk=pk, department=dept)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "comment":
            DocumentComment.objects.create(
                document=doc, user=request.user,
                comment=request.POST.get("comment", ""),
                file=request.FILES.get("file"),
            )
            messages.success(request, "Comment added.")
        return redirect("department_document_detail", pk=pk)

    return render(request, "department/document_detail.html", {"doc": doc})


@login_required
@user_passes_test(is_dept_officer)
def start_review(request, pk):
    dept = request.user.profile.department
    doc = get_object_or_404(Document, pk=pk, department=dept, status="forwarded_to_dept")
    transition_document(doc, "under_dept_review", request.user, "Department review started")
    doc.current_holder = f"{dept.name} Office (Under Review)"
    doc.save()
    messages.success(request, "Review started. Process the document and add comments as needed.")
    return redirect("department_document_detail", pk=pk)


@login_required
@user_passes_test(is_dept_officer)
def mark_solved(request, pk):
    dept = request.user.profile.department
    doc = get_object_or_404(Document, pk=pk, department=dept, status="under_dept_review")

    if request.method == "POST":
        signature_file = request.FILES.get("signature")
        remarks = request.POST.get("remarks", "")

        Signature.objects.create(
            document=doc,
            user=request.user,
            role=f"Department Officer ({dept.name})",
            signature_image=signature_file or "",
            remarks=remarks,
        )

        transition_document(doc, "awaiting_director", request.user, remarks or "Department processing complete")
        doc.current_holder = "Director's Office"
        doc.save()
        notify_status_change(doc)
        messages.success(request, "Document signed and forwarded to Director.")
        return redirect("department_dashboard")

    return render(request, "department/mark_solved.html", {"doc": doc})


@login_required
@user_passes_test(is_dept_officer)
def return_for_revision(request, pk):
    dept = request.user.profile.department
    doc = get_object_or_404(Document, pk=pk, department=dept, status="under_dept_review")

    if request.method == "POST":
        comment = request.POST.get("comment", "")
        transition_document(doc, "forwarded_to_dept", request.user, f"Returned for revision: {comment}")
        doc.current_holder = f"{dept.name} Office (Returned for Revision)"
        doc.save()
        messages.info(request, "Document returned for revision.")
        return redirect("department_dashboard")

    return render(request, "department/return_revision.html", {"doc": doc})
