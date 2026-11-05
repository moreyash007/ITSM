from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from itsm.dashboard import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('users/', include('users.urls', namespace='users')),
    path('tickets/', include('tickets.urls', namespace='tickets')),
    path('incidents/', include('incidents.urls', namespace='incidents')),
    path('changes/', include('changes.urls', namespace='changes')),
    path('assets/', include('assets.urls', namespace='assets')),
    path('api/', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
