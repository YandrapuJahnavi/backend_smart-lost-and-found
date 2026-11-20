from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.contrib.auth import get_user_model
from django.db.models import Count
from items.models import LostItem, FoundItem
from matching.models import MatchRecord
from claims.models import Claim

User = get_user_model()

class IsAdminUserOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.is_staff))

class AdminDashboardStatsView(APIView):
    """
    GET /api/admin/stats/
    Provides comprehensive statistical overview for the administrative dashboard.
    """
    permission_classes = [IsAdminUserOrStaff]

    def get(self, request):
        total_users = User.objects.count()
        total_lost = LostItem.objects.count()
        total_found = FoundItem.objects.count()
        total_matches = MatchRecord.objects.count()
        pending_claims = Claim.objects.filter(status='pending').count()
        resolved_cases = (
            LostItem.objects.filter(status='resolved').count() +
            FoundItem.objects.filter(status='resolved').count() +
            Claim.objects.filter(status='approved').count()
        )

        # Recent activities with ISO formatted timestamps
        recent_lost = [
            {
                'id': item.id,
                'title': item.title,
                'category': item.category,
                'status': item.status,
                'created_at': item.created_at.isoformat()
            }
            for item in LostItem.objects.all().order_by('-created_at')[:5]
        ]

        recent_found = [
            {
                'id': item.id,
                'title': item.title,
                'category': item.category,
                'status': item.status,
                'created_at': item.created_at.isoformat()
            }
            for item in FoundItem.objects.all().order_by('-created_at')[:5]
        ]

        recent_claims = [
            {
                'id': c.id,
                'claimant_username': c.claimant.username,
                'status': c.status,
                'created_at': c.created_at.isoformat()
            }
            for c in Claim.objects.select_related('claimant').order_by('-created_at')[:5]
        ]

        recent_matches = [
            {
                'id': m.id,
                'lost_item_title': m.lost_item.title,
                'found_item_title': m.found_item.title,
                'similarity_score': m.similarity_score,
                'status': m.status,
                'created_at': m.created_at.isoformat()
            }
            for m in MatchRecord.objects.select_related('lost_item', 'found_item').order_by('-created_at')[:5]
        ]

        # Category breakdown
        lost_by_cat = dict(LostItem.objects.values_list('category').annotate(c=Count('id')))
        found_by_cat = dict(FoundItem.objects.values_list('category').annotate(c=Count('id')))

        return Response({
            "total_users": total_users,
            "total_lost_reports": total_lost,
            "total_found_reports": total_found,
            "total_matches": total_matches,
            "pending_claims": pending_claims,
            "resolved_cases": resolved_cases,
            "recent_lost": recent_lost,
            "recent_found": recent_found,
            "recent_claims": recent_claims,
            "recent_matches": recent_matches,
            "category_distribution": {
                "lost": lost_by_cat,
                "found": found_by_cat
            }
        })
