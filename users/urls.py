from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.change_password_view, name='change_password'),
    path('manage/', views.user_list_view, name='list'),
    path('manage/create/', views.user_create_view, name='create'),
    path('manage/<int:pk>/edit/', views.user_edit_view, name='edit'),
    path('manage/<int:pk>/toggle/', views.user_toggle_active_view, name='toggle'),
]
