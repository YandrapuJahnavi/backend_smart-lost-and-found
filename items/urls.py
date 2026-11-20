from django.urls import path
from .views import (
    LostItemListCreateView,
    LostItemDetailView,
    FoundItemListCreateView,
    FoundItemDetailView,
    NearbyItemsView
)

urlpatterns = [
    # Nearby items
    path('nearby/', NearbyItemsView.as_view(), name='items_nearby'),
]

