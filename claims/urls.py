from django.urls import path
from .views import ClaimListCreateView, ClaimDetailView, ClaimStatusUpdateView

urlpatterns = [
    path('', ClaimListCreateView.as_view(), name='claims_list_create'),
    path('<int:pk>/', ClaimDetailView.as_view(), name='claims_detail'),
    path('<int:pk>/status/', ClaimStatusUpdateView.as_view(), name='claims_status_update'),
]

