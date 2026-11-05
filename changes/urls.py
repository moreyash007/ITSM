from django.urls import path
from . import views

app_name = 'changes'

urlpatterns = [
    path('', views.change_list, name='list'),
    path('create/', views.change_create, name='create'),
    path('<int:pk>/', views.change_detail, name='detail'),
    path('<int:pk>/edit/', views.change_edit, name='edit'),
    path('<int:pk>/submit/', views.change_submit, name='submit'),
]
