from django import forms
from django.core.exceptions import ValidationError
from .models import Document


def validate_pdf(file):
    if file.content_type != "application/pdf":
        raise ValidationError("Only PDF files are accepted.")
    if not file.name.lower().endswith(".pdf"):
        raise ValidationError("File must have a .pdf extension.")


class DocumentRegistryForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            "applicant_name", "applicant_email", "applicant_phone",
            "title", "description", "department", "category",
            "submission_type", "uploaded_file", "priority",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "class": "w-full rounded-md border border-[#c8c8c8] px-3 py-2 text-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "w-full rounded-md border border-[#c8c8c8] px-3 py-2 text-sm focus:border-[#0067c0] focus:outline-none"
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", css)
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", css)
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.setdefault("class", css)
                field.widget.attrs.setdefault("accept", "application/pdf")
            else:
                field.widget.attrs.setdefault("class", css)

    def clean_uploaded_file(self):
        f = self.cleaned_data.get("uploaded_file")
        if f:
            validate_pdf(f)
        return f


class DocumentSoftcopyForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "description", "department", "category", "uploaded_file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "class": "w-full rounded-md border border-[#c8c8c8] px-3 py-2 text-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "w-full rounded-md border border-[#c8c8c8] px-3 py-2 text-sm focus:border-[#0067c0] focus:outline-none"
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", css)
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", css)
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.setdefault("class", css + " file:mr-3 file:rounded file:border-0 file:bg-[#eaf4ff] file:px-3 file:py-1 file:text-xs file:font-semibold file:text-[#0067c0]")
                field.widget.attrs.setdefault("accept", "application/pdf")
            else:
                field.widget.attrs.setdefault("class", css)

    def clean_uploaded_file(self):
        f = self.cleaned_data.get("uploaded_file")
        if f:
            validate_pdf(f)
        return f


class DirectorDecisionForm(forms.Form):
    DECISIONS = [
        ("approve", "Approve"),
        ("return", "Return for Correction"),
    ]
    decision = forms.ChoiceField(choices=DECISIONS, widget=forms.RadioSelect(attrs={"class": "mr-2"}))
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "w-full rounded-md border border-[#c8c8c8] px-3 py-2 text-sm", "placeholder": "Add remarks..."}),
        required=False,
    )
    external_signed_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"accept": ".pdf,application/pdf", "class": "w-full rounded-md border border-[#c8c8c8] px-3 py-2 text-sm"}),
        help_text="Upload an externally signed/stamped PDF for integrity cross-check.",
    )

    def clean_external_signed_file(self):
        f = self.cleaned_data.get("external_signed_file")
        if f and f.content_type != "application/pdf":
            raise ValidationError("Only PDF files are accepted.")
        return f
