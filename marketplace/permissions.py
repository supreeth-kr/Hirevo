from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework import permissions


def client_required(view_func):
    """View decorator to ensure user is authenticated and has client role."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")
        if not request.user.is_client():
            raise PermissionDenied("Access restricted to Client accounts.")
        return view_func(request, *args, **kwargs)
    return wrapper


def freelancer_required(view_func):
    """View decorator to ensure user is authenticated and has freelancer role."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")
        if not request.user.is_freelancer():
            raise PermissionDenied("Access restricted to Freelancer accounts.")
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """View decorator to ensure user is authenticated and is staff or administrator."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/admin-login/?next={request.path}")
        if not request.user.is_admin_user():
            raise PermissionDenied("Access restricted to Administrators.")
        return view_func(request, *args, **kwargs)
    return wrapper


# DRF API Permissions
class IsClientUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_client())


class IsFreelancerUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_freelancer())


class IsAdminUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_user())
