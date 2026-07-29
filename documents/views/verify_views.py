from django.shortcuts import render, get_object_or_404, redirect
from ..models import Document
from ..utils import verify_document_integrity


def verify_document(request, document_id):
    doc = get_object_or_404(Document, document_id=document_id)
    ds = doc.digital_signatures.first()
    result = None
    if ds:
        valid, msg = verify_document_integrity(doc)
        result = {"valid": valid, "message": msg}
    return render(request, "verify_document.html", {
        "doc": doc,
        "digital_signature": ds,
        "result": result,
    })


def verify_lookup(request):
    q = request.GET.get("q", "").strip()
    if q:
        return redirect("verify_document", document_id=q)
    return render(request, "verify_document.html", {"doc": None, "digital_signature": None, "result": None})
