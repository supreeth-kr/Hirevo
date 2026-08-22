from django.core.exceptions import PermissionDenied
from functools import wraps
from django.shortcuts import redirect


def client_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_client():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def freelancer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_freelancer():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin_user():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
