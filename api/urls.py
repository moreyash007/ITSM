from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from .views import (
    TicketViewSet, CategoryViewSet,
    IncidentViewSet,
    ChangeRequestViewSet,
    AssetViewSet, AssetCategoryViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'tickets-categories', CategoryViewSet, basename='ticket-category')
router.register(r'incidents', IncidentViewSet, basename='incident')
router.register(r'changes', ChangeRequestViewSet, basename='change')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'asset-categories', AssetCategoryViewSet, basename='asset-category')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    # Auth
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    # OpenAPI schema & docs
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
