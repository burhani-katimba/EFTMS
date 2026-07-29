import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="categories")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "department")

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("registry", "Registrar"),
        ("department", "Department Officer"),
        ("director", "Director"),
        ("applicant", "Applicant"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="applicant")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="officers")
    phone = models.CharField(max_length=20, blank=True)
    signature = models.ImageField(upload_to="signatures/", blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class Document(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("under_registry_review", "Under Registry Review"),
        ("registered", "Registered"),
        ("forwarded_to_dept", "Forwarded to Department"),
        ("under_dept_review", "Under Department Review"),
        ("awaiting_director", "Awaiting Director Approval"),
        ("approved", "Approved"),
        ("returned_to_registry", "Returned to Registry"),
        ("ready_for_collection", "Ready for Collection"),
        ("collected", "Collected"),
    ]

    VALID_TRANSITIONS = {
        "submitted": ["under_registry_review"],
        "under_registry_review": ["registered"],
        "registered": ["forwarded_to_dept"],
        "forwarded_to_dept": ["under_dept_review"],
        "under_dept_review": ["awaiting_director", "forwarded_to_dept"],
        "awaiting_director": ["approved", "under_dept_review"],
        "approved": ["returned_to_registry"],
        "returned_to_registry": ["ready_for_collection"],
        "ready_for_collection": ["collected"],
    }

    SUBMISSION_CHOICES = [
        ("physical", "Physical Submission"),
        ("softcopy", "Softcopy Submission"),
    ]

    document_id = models.CharField(max_length=30, unique=True, editable=False)
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True)

    applicant_name = models.CharField(max_length=200)
    applicant_email = models.EmailField()
    applicant_phone = models.CharField(max_length=20, blank=True)

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name="documents")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")

    submission_type = models.CharField(max_length=20, choices=SUBMISSION_CHOICES)
    uploaded_file = models.FileField(upload_to="documents/", blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="submitted")
    priority = models.CharField(
        max_length=10, choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium"
    )

    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_documents"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    registered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="registered_documents"
    )
    registered_at = models.DateTimeField(null=True, blank=True)

    current_holder = models.CharField(max_length=100, blank=True, default="")

    director_approval = models.BooleanField(null=True, blank=True)
    director_remarks = models.TextField(blank=True)
    director_signed_at = models.DateTimeField(null=True, blank=True)

    municipal_stamp = models.ImageField(upload_to="stamps/", blank=True)

    ready_for_collection_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.document_id} - {self.title}"

    def can_transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status):
        if not self.can_transition_to(new_status):
            raise ValueError(f"Cannot transition from '{self.status}' to '{new_status}'")
        from_status = self.status
        self.status = new_status
        self.save()
        return from_status

    document_hash = models.CharField(max_length=64, blank=True, editable=False,
        help_text="SHA-256 hex digest of the uploaded file at time of signing")
    certified_file = models.FileField(upload_to="certified/", blank=True,
        help_text="Stamped PDF with QR overlay + signature metadata")
    integrity_verified_at = models.DateTimeField(null=True, blank=True,
        help_text="Last time integrity check passed")
    external_signed_file = models.FileField(upload_to="external_signed/", blank=True,
        help_text="Externally signed PDF uploaded by Director for cross-check")

    def save(self, *args, **kwargs):
        if not self.document_id:
            year = timezone.now().year
            count = Document.objects.filter(created_at__year=year).count() + 1
            self.document_id = f"MCD-{year}-{count:04d}"
        super().save(*args, **kwargs)


class DigitalSignature(models.Model):
    ALGORITHM_CHOICES = [
        ("RSA-PSS-SHA256", "RSA-PSS SHA-256"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="digital_signatures")
    algorithm = models.CharField(max_length=30, choices=ALGORITHM_CHOICES, default="RSA-PSS-SHA256")
    document_hash = models.CharField(max_length=64, editable=False, help_text="SHA-256 hex of the file")
    signature_value = models.TextField(editable=False, help_text="Hex-encoded RSA-PSS signature")
    signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    signed_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(null=True, blank=True, help_text="Last verification result")
    verified_at = models.DateTimeField(null=True, blank=True)
    certificate_fingerprint = models.CharField(max_length=64, blank=True, help_text="SHA-256 of public key PEM")

    class Meta:
        ordering = ["-signed_at"]

    def __str__(self):
        return f"DigitalSig {self.document.document_id} @ {self.signed_at}"


class DocumentLog(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="logs")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.document.document_id}: {self.from_status} -> {self.to_status}"


class DocumentComment(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    file = models.FileField(upload_to="supporting_docs/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.document.document_id}"


class Signature(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="signatures")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50)
    signature_image = models.ImageField(upload_to="signatures/", blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["signed_at"]

    def __str__(self):
        return f"{self.user.username} signed {self.document.document_id} as {self.role}"


class Notification(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="notifications")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=300)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.document.document_id}: {self.subject[:50]}"
