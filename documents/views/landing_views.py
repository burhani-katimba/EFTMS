from django.shortcuts import render
from ..models import Department


def home(request):
    departments = Department.objects.filter(is_active=True)
    return render(request, "landing.html", {"departments": departments})
