from django.urls import path
from .views import MatchListView, MatchDetailView, MatchGenerateView

urlpatterns = [
    path('', MatchListView.as_view(), name='matches_list'),
    path('<int:pk>/', MatchDetailView.as_view(), name='matches_detail'),
    path('generate/', MatchGenerateView.as_view(), name='matches_generate'),
]

