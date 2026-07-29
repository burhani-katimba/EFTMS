from django.urls import path
from .views import auth_views, registry_views, department_views, director_views, user_views, admin_views, landing_views, verify_views

urlpatterns = [
    path("", landing_views.home, name="home"),

    path("login/", auth_views.login_view, name="login"),
    path("logout/", auth_views.logout_view, name="logout"),

    path("dashboard/", user_views.dashboard, name="user_dashboard"),
    path("submit/", user_views.submit_document, name="user_submit"),
    path("track/<int:pk>/", user_views.track_document, name="user_track"),
    path("notifications/", user_views.notifications_view, name="user_notifications"),
    path("track/<str:document_id>/", user_views.public_track, name="public_track"),

    path("registry/", registry_views.dashboard, name="registry_dashboard"),
    path("registry/all/", registry_views.all_documents, name="registry_all_documents"),
    path("registry/register/", registry_views.register_document, name="registry_register"),
    path("registry/<int:pk>/review/", registry_views.review_document, name="registry_review"),
    path("registry/<int:pk>/", registry_views.document_detail, name="registry_document_detail"),
    path("registry/<int:pk>/forward/", registry_views.forward_to_department, name="registry_forward"),
    path("registry/<int:pk>/ready/", registry_views.mark_ready, name="registry_mark_ready"),
    path("registry/<int:pk>/collect/", registry_views.mark_collected, name="registry_mark_collected"),

    path("department/", department_views.dashboard, name="department_dashboard"),
    path("department/pending/", department_views.pending_list, name="department_pending_list"),
    path("department/reviewing/", department_views.reviewing_list, name="department_reviewing_list"),
    path("department/<int:pk>/", department_views.document_detail, name="department_document_detail"),
    path("department/<int:pk>/start-review/", department_views.start_review, name="department_start_review"),
    path("department/<int:pk>/mark-solved/", department_views.mark_solved, name="department_mark_solved"),
    path("department/<int:pk>/return-revision/", department_views.return_for_revision, name="department_return_revision"),

    path("director/", director_views.dashboard, name="director_dashboard"),
    path("director/pending/", director_views.all_pending, name="director_all_pending"),
    path("director/<int:pk>/", director_views.document_detail, name="director_document_detail"),

    path("admin-panel/", admin_views.dashboard, name="admin_dashboard"),
    path("admin-panel/users/", admin_views.manage_users, name="admin_manage_users"),
    path("admin-panel/logs/", admin_views.list_logs, name="admin_list_logs"),
    path("admin-panel/comments/", admin_views.list_comments, name="admin_list_comments"),
    path("admin-panel/signatures/", admin_views.list_signatures, name="admin_list_signatures"),
    path("admin-panel/notifications/", admin_views.list_notifications, name="admin_list_notifications"),
    path("admin-panel/departments/", admin_views.list_departments, name="admin_list_departments"),
    path("admin-panel/categories/", admin_views.list_categories, name="admin_list_categories"),
    path("admin-panel/documents/", admin_views.list_documents, name="admin_list_documents"),

    path("verify/<str:document_id>/", verify_views.verify_document, name="verify_document"),
    path("verify/", verify_views.verify_lookup, name="verify_lookup"),
]
