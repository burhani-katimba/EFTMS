from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from ..models import UserProfile


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect(request.user))
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(_role_redirect(user))
        messages.error(request, "Invalid username or password.")
    return render(request, "registration/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def _role_redirect(user):
    if not hasattr(user, "profile"):
        UserProfile.objects.get_or_create(user=user)
    role = user.profile.role
    if role == "registry":
        return "registry_dashboard"
    elif role == "department":
        return "department_dashboard"
    elif role == "director":
        return "director_dashboard"
    elif role == "admin":
        return "admin_dashboard"
    return "user_dashboard"
