from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.ticket_list, name='list'),
    path('create/', views.ticket_create, name='create'),
    path('<int:pk>/', views.ticket_detail, name='detail'),
    path('<int:pk>/edit/', views.ticket_edit, name='edit'),
    path('<int:pk>/resolve/', views.ticket_resolve, name='resolve'),
    path('<int:pk>/close/', views.ticket_close, name='close'),
]
