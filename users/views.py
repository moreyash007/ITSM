from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import User
from .forms import LoginForm, UserRegistrationForm, UserProfileForm, ChangePasswordForm
from .decorators import admin_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect('tickets:list')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(request.GET.get('next', 'tickets:list'))
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('users:login')


@login_required
def profile_view(request):
    form = UserProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('users:profile')
    return render(request, 'users/profile.html', {'form': form})


@login_required
def change_password_view(request):
    form = ChangePasswordForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed successfully.')
        return redirect('users:profile')
    return render(request, 'users/change_password.html', {'form': form})


@admin_required
def user_list_view(request):
    users = User.objects.all().order_by('username')
    paginator = Paginator(users, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'users/user_list.html', {'page_obj': page})


@admin_required
def user_create_view(request):
    form = UserRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User created successfully.')
        return redirect('users:list')
    return render(request, 'users/user_form.html', {'form': form, 'title': 'Create User'})


@admin_required
def user_edit_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserProfileForm(request.POST or None, request.FILES or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User updated successfully.')
        return redirect('users:list')
    return render(request, 'users/user_form.html', {'form': form, 'title': f'Edit {user.username}'})


@admin_required
def user_toggle_active_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user != request.user:
        user.is_active = not user.is_active
        user.save()
        status = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'User {user.username} {status}.')
    return redirect('users:list')
