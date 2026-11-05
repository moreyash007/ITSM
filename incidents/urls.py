from django.urls import path
from . import views

app_name = 'incidents'

urlpatterns = [
    path('', views.incident_list, name='list'),
    path('create/', views.incident_create, name='create'),
    path('<int:pk>/', views.incident_detail, name='detail'),
    path('<int:pk>/edit/', views.incident_edit, name='edit'),
]
