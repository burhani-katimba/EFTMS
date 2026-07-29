from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Department, Category, UserProfile, Document, DocumentLog, DocumentComment, Signature, Notification


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ["username", "email", "get_role", "is_staff"]
    list_filter = ["profile__role"]

    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, "profile") else "-"
    get_role.short_description = "Role"
    get_role.admin_order_field = "profile__role"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "created_at"]
    search_fields = ["name"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "department"]
    list_filter = ["department"]
    search_fields = ["name", "department__name"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "document_id", "title", "status", "current_holder",
        "department", "submission_type", "created_at"
    ]
    list_filter = ["status", "department", "submission_type", "priority"]
    search_fields = ["document_id", "title", "applicant_name"]
    readonly_fields = ["document_id", "qr_code", "created_at", "updated_at"]


@admin.register(DocumentLog)
class DocumentLogAdmin(admin.ModelAdmin):
    list_display = ["document", "from_status", "to_status", "changed_by", "created_at"]
    list_filter = ["to_status"]


@admin.register(DocumentComment)
class DocumentCommentAdmin(admin.ModelAdmin):
    list_display = ["document", "user", "created_at"]


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ["document", "user", "role", "signed_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["document", "recipient_email", "subject", "is_sent", "created_at"]
    list_filter = ["is_sent"]
