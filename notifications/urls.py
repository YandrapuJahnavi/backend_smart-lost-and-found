from django.urls import path
from .views import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    NotificationUnreadCountView
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notifications_list'),
    path('<int:pk>/read/', NotificationMarkReadView.as_view(), name='notifications_mark_read'),
    path('read-all/', NotificationMarkAllReadView.as_view(), name='notifications_mark_all_read'),
    path('unread-count/', NotificationUnreadCountView.as_view(), name='notifications_unread_count'),
]

