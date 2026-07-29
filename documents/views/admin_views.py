from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.db.models import Count, Q
from ..models import Document, Department, Category, UserProfile, DocumentLog, DocumentComment, Signature, Notification


def _paginate(queryset, request, per_page=25):
    """Paginate a queryset and return (page_obj, filter_params_str)."""
    page = request.GET.get("page", 1)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)
    filter_params = request.GET.copy()
    filter_params.pop("page", None)
    filter_params_str = filter_params.urlencode() if filter_params else ""
    return page_obj, filter_params_str


def _date_filter(request, queryset, field="created_at"):
    """Apply optional date_from/date_to filters from GET params."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    quick = request.GET.get("quick")
    from datetime import datetime, timedelta
    today = datetime.now().date()
    if quick == "today":
        date_from = today.isoformat()
        date_to = today.isoformat()
    elif quick == "week":
        monday = today - timedelta(days=today.weekday())
        date_from = monday.isoformat()
        date_to = today.isoformat()
    elif quick == "month":
        date_from = today.replace(day=1).isoformat()
        date_to = today.isoformat()
    if date_from:
        try:
            queryset = queryset.filter(**{f"{field}__gte": datetime.strptime(date_from, "%Y-%m-%d")})
        except ValueError:
            pass
    if date_to:
        try:
            queryset = queryset.filter(**{f"{field}__lte": datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)})
        except ValueError:
            pass
    return queryset


@staff_member_required
def dashboard(request):
    import os
    from django.conf import settings
    media_path = settings.MEDIA_ROOT
    total_size = 0
    if media_path.exists():
        for f in media_path.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
    media_size_mb = round(total_size / (1024 * 1024), 1)

    total = Document.objects.count()
    pending_dept = Document.objects.filter(status="forwarded_to_dept").count()
    pending_director = Document.objects.filter(status="awaiting_director").count()
    approved = Document.objects.filter(status="approved").count()
    collected = Document.objects.filter(status="collected").count()
    ready = Document.objects.filter(status="ready_for_collection").count()
    under_review = Document.objects.filter(status="under_dept_review").count()

    dept_stats = Department.objects.annotate(
        total_docs=Count("documents"),
        pending_docs=Count("documents", filter=Q(documents__status="forwarded_to_dept")),
    ).order_by("-total_docs")

    recent_logs = DocumentLog.objects.select_related("document", "changed_by").order_by("-created_at")[:5]
    recent_notifs = Notification.objects.order_by("-created_at")[:5]

    failed_notifs = Notification.objects.filter(is_sent=False).count()
    user_count = User.objects.count()

    return render(request, "admin_docs/dashboard.html", {
        "total": total,
        "pending_dept": pending_dept,
        "pending_director": pending_director,
        "approved": approved,
        "collected": collected,
        "ready": ready,
        "under_review": under_review,
        "dept_stats": dept_stats,
        "recent_logs": recent_logs,
        "recent_notifs": recent_notifs,
        "media_size_mb": media_size_mb,
        "failed_notifs": failed_notifs,
        "user_count": user_count,
    })


@staff_member_required
def manage_users(request):
    users = User.objects.select_related("profile").all().order_by("-date_joined")
    departments = Department.objects.filter(is_active=True)
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        action = request.POST.get("action")
        target_user = get_object_or_404(User, pk=user_id) if user_id else None

        if action == "create" and request.POST.get("username"):
            u = User.objects.create_user(
                username=request.POST["username"],
                email=request.POST.get("email", ""),
                password=request.POST.get("password", "changeme123"),
            )
            UserProfile.objects.create(
                user=u,
                role=request.POST.get("role", "applicant"),
                department_id=request.POST.get("department") or None,
            )
            messages.success(request, f"User {u.username} created.")
        elif action == "deactivate" and target_user:
            target_user.is_active = False
            target_user.save()
            messages.success(request, f"User {target_user.username} deactivated.")
        elif action == "activate" and target_user:
            target_user.is_active = True
            target_user.save()
            messages.success(request, f"User {target_user.username} activated.")
        elif action == "change_role" and target_user:
            profile, _ = UserProfile.objects.get_or_create(user=target_user)
            profile.role = request.POST.get("role", "applicant")
            profile.department_id = request.POST.get("department") or None
            profile.save()
            messages.success(request, f"User {target_user.username} role updated.")
        elif action == "reset_password" and target_user:
            new_pass = request.POST.get("new_password", "changeme123")
            target_user.set_password(new_pass)
            target_user.save()
            messages.success(request, f"Password reset for {target_user.username}.")
        return redirect("admin_manage_users")

    page_obj, filter_str = _paginate(users, request)
    return render(request, "admin_docs/manage_users.html", {
        "page_obj": page_obj,
        "departments": departments,
        "filter_params": filter_str,
    })


@staff_member_required
def list_logs(request):
    qs = DocumentLog.objects.select_related("document", "changed_by").order_by("-created_at")
    qs = _date_filter(request, qs)
    page_obj, filter_str = _paginate(qs, request)
    return render(request, "admin_docs/list_logs.html", {"page_obj": page_obj, "filter_params": filter_str})


@staff_member_required
def list_comments(request):
    qs = DocumentComment.objects.select_related("document", "user").order_by("-created_at")
    qs = _date_filter(request, qs)
    page_obj, filter_str = _paginate(qs, request)
    return render(request, "admin_docs/list_comments.html", {"page_obj": page_obj, "filter_params": filter_str})


@staff_member_required
def list_signatures(request):
    qs = Signature.objects.select_related("document", "user").order_by("-signed_at")
    qs = _date_filter(request, qs, field="signed_at")
    page_obj, filter_str = _paginate(qs, request)
    return render(request, "admin_docs/list_signatures.html", {"page_obj": page_obj, "filter_params": filter_str})


@staff_member_required
def list_notifications(request):
    qs = Notification.objects.order_by("-created_at")
    qs = _date_filter(request, qs)
    page_obj, filter_str = _paginate(qs, request)
    return render(request, "admin_docs/list_notifications.html", {"page_obj": page_obj, "filter_params": filter_str})


@staff_member_required
def list_departments(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            Department.objects.create(
                name=request.POST["name"],
                description=request.POST.get("description", ""),
                is_active=request.POST.get("is_active") == "on",
            )
            messages.success(request, "Department created.")
        elif action == "toggle":
            dept = get_object_or_404(Department, pk=request.POST.get("dept_id"))
            dept.is_active = not dept.is_active
            dept.save()
        return redirect("admin_list_departments")
    depts = Department.objects.annotate(
        total_docs=Count("documents"),
        pending_docs=Count("documents", filter=Q(documents__status="forwarded_to_dept")),
    ).order_by("name")
    page_obj, filter_str = _paginate(depts, request)
    return render(request, "admin_docs/list_departments.html", {"page_obj": page_obj, "filter_params": filter_str})


@staff_member_required
def list_categories(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            Category.objects.create(
                name=request.POST["name"],
                department_id=request.POST.get("department"),
                description=request.POST.get("description", ""),
            )
            messages.success(request, "Category created.")
        elif action == "delete":
            Category.objects.filter(pk=request.POST.get("cat_id")).delete()
            messages.success(request, "Category deleted.")
        return redirect("admin_list_categories")
    cats = Category.objects.select_related("department").order_by("department__name", "name")
    departments = Department.objects.filter(is_active=True)
    page_obj, filter_str = _paginate(cats, request)
    return render(request, "admin_docs/list_categories.html", {"page_obj": page_obj, "departments": departments, "filter_params": filter_str})


@staff_member_required
def list_documents(request):
    qs = Document.objects.select_related("department", "submitted_by").order_by("-created_at")
    qs = _date_filter(request, qs)
    page_obj, filter_str = _paginate(qs, request)
    return render(request, "admin_docs/list_documents.html", {"page_obj": page_obj, "filter_params": filter_str})
