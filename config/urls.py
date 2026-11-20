from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from items.views import (
    LostItemListCreateView,
    LostItemDetailView,
    FoundItemListCreateView,
    FoundItemDetailView,
    NearbyItemsView,
)
from accounts.dashboard_views import AdminDashboardStatsView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication
    path('api/auth/', include('accounts.urls')),

    # Lost Items endpoints
    path('api/lost-items/', LostItemListCreateView.as_view(), name='lost_items_list_create'),
    path('api/lost-items/<int:pk>/', LostItemDetailView.as_view(), name='lost_items_detail'),

    # Found Items endpoints
    path('api/found-items/', FoundItemListCreateView.as_view(), name='found_items_list_create'),
    path('api/found-items/<int:pk>/', FoundItemDetailView.as_view(), name='found_items_detail'),

    # Location & Nearby Items endpoint
    path('api/items/nearby/', NearbyItemsView.as_view(), name='items_nearby'),

    # AI Matching endpoints
    path('api/matches/', include('matching.urls')),

    # In-App Notifications endpoints
    path('api/notifications/', include('notifications.urls')),

    # Ownership Claims endpoints
    path('api/claims/', include('claims.urls')),

    # Admin Dashboard statistics
    path('api/admin/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
