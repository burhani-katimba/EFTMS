from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from ..models import Document, Department, Category
from ..forms import DocumentRegistryForm
from ..utils import generate_qr_code, sign_and_stamp_document, transition_document, notify_status_change
from ..templatetags.document_extras import STATUS_ORDER


def is_registry(user):
    return hasattr(user, "profile") and user.profile.role == "registry"


@login_required
@user_passes_test(is_registry)
def dashboard(request):
    pending_softcopies = Document.objects.filter(
        submission_type="softcopy", status="submitted", registered_by__isnull=True
    ).order_by("-created_at")
    documents = Document.objects.filter(registered_by=request.user).order_by("-created_at")
    from django.utils import timezone
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_registered = documents.filter(created_at__gte=today_start).count()
    today_forwarded = Document.objects.filter(registered_by=request.user, status="forwarded_to_dept", created_at__gte=today_start).count()
    stats = {
        "total": documents.count(),
        "pending_softcopy_count": pending_softcopies.count(),
        "with_dept": documents.filter(status="forwarded_to_dept").count(),
        "ready": documents.filter(status="ready_for_collection").count(),
        "collected": documents.filter(status="collected").count(),
        "today_registered": today_registered,
        "today_forwarded": today_forwarded,
    }
    view = request.GET.get("view")
    all_docs = Document.objects.filter(registered_by=request.user).order_by("-created_at")
    if view == "registered":
        filtered = all_docs.filter(status__in=["registered", "under_registry_review"])
    elif view == "forwarded":
        filtered = all_docs.filter(status__in=["forwarded_to_dept", "under_dept_review", "awaiting_director"])
    elif view == "ready":
        filtered = all_docs.filter(status__in=["returned_to_registry", "ready_for_collection", "collected"])
    else:
        filtered = documents[:5]
    return render(request, "registry/dashboard.html", {
        "documents": documents[:5], "pending_softcopies": pending_softcopies[:5], "filtered_docs": filtered, **stats,
    })


@login_required
@user_passes_test(is_registry)
def all_documents(request):
    qs = Document.objects.filter(registered_by=request.user).order_by("-created_at")
    page = request.GET.get("page", 1)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)
    return render(request, "registry/all_documents.html", {"page_obj": page_obj})


@login_required
@user_passes_test(is_registry)
def register_document(request):
    if request.method == "POST":
        form = DocumentRegistryForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.registered_by = request.user
            doc.current_holder = "Registry Office"
            doc.save()
            generate_qr_code(doc)
            sign_and_stamp_document(doc, request.user)
            DocumentLog.objects.create(
                document=doc, from_status="", to_status="under_registry_review",
                changed_by=request.user, comment="Document registered by registrar",
            )
            messages.success(request, f"Document {doc.document_id} registered. Review the PDF before forwarding.")
            return redirect("registry_review", pk=doc.id)
    else:
        form = DocumentRegistryForm()
    return render(request, "registry/register_form.html", {"form": form})


@login_required
@user_passes_test(is_registry)
def review_document(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if doc.status not in ("under_registry_review", "submitted"):
        messages.warning(request, "Document is not in review stage.")
        return redirect("registry_dashboard")
    if doc.registered_by is None:
        doc.registered_by = request.user

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "confirm":
            doc.registered_at = timezone.now()
            if doc.status == "submitted":
                transition_document(doc, "under_registry_review", request.user, "Review started for softcopy submission")
            transition_document(doc, "registered", request.user, "Registration confirmed after review")
            doc.current_holder = "Registry Office"
            doc.save()
            generate_qr_code(doc)
            sign_and_stamp_document(doc, request.user)
            notify_status_change(doc)
            messages.success(request, "Document registered successfully. Forward to department?")
            return redirect("registry_forward", pk=doc.id)
        elif action == "edit":
            for field in ["applicant_name", "applicant_email", "applicant_phone", "title", "description", "priority"]:
                val = request.POST.get(field)
                if val is not None:
                    setattr(doc, field, val)
            dept_id = request.POST.get("department")
            if dept_id:
                doc.department_id = dept_id
            cat_id = request.POST.get("category")
            if cat_id:
                doc.category_id = cat_id
            doc.save()
            messages.success(request, "Document updated.")
            return redirect("registry_review", pk=doc.id)

    return render(request, "registry/review_document.html", {
        "doc": doc,
        "departments": Department.objects.filter(is_active=True),
        "categories": Category.objects.filter(department=doc.department) if doc.department else [],
    })


@login_required
@user_passes_test(is_registry)
def document_detail(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    return render(request, "registry/document_detail.html", {"doc": doc})


@login_required
@user_passes_test(is_registry)
def forward_to_department(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if doc.status != "registered":
        messages.warning(request, "Document must be registered before forwarding.")
        return redirect("registry_dashboard")

    if request.method == "POST":
        dept_id = request.POST.get("department")
        comment = request.POST.get("comment", "")
        doc.department_id = dept_id
        doc.current_holder = f"{Department.objects.get(pk=dept_id).name} Office"
        transition_document(doc, "forwarded_to_dept", request.user, comment)
        notify_status_change(doc)
        messages.success(request, f"Document forwarded to {doc.department.name}.")
        return redirect("registry_dashboard")

    departments = Department.objects.filter(is_active=True)
    return render(request, "registry/forward_department.html", {"doc": doc, "departments": departments})


@login_required
@user_passes_test(is_registry)
def mark_ready(request, pk):
    doc = get_object_or_404(Document, pk=pk, registered_by=request.user)
    if doc.status not in ("returned_to_registry", "approved"):
        messages.warning(request, "Document must be returned from Director first.")
        return redirect("registry_dashboard")

    doc.ready_for_collection_at = timezone.now()
    transition_document(doc, "ready_for_collection", request.user, "Document ready for collection")
    doc.current_holder = "Registry Office (Ready for Collection)"
    doc.save()
    notify_status_change(doc)
    messages.success(request, "Document marked as ready for collection.")
    return redirect("registry_dashboard")


@login_required
@user_passes_test(is_registry)
def mark_collected(request, pk):
    doc = get_object_or_404(Document, pk=pk, registered_by=request.user)
    if doc.status != "ready_for_collection":
        messages.warning(request, "Document must be ready for collection first.")
        return redirect("registry_dashboard")

    doc.collected_at = timezone.now()
    transition_document(doc, "collected", request.user, "Document collected by applicant")
    doc.current_holder = "Collected"
    doc.save()
    notify_status_change(doc)
    messages.success(request, "Document marked as collected.")
    return redirect("registry_dashboard")
