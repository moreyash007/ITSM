from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def agent_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if not request.user.is_agent:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('tickets:list')
        return view_func(request, *args, **kwargs)
    return _wrapped


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if not request.user.is_admin_role:
            messages.error(request, 'Admin access required.')
            return redirect('tickets:list')
        return view_func(request, *args, **kwargs)
    return _wrapped
