from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from .models import MatchRecord
from .serializers import MatchRecordSerializer
from items.models import LostItem, FoundItem
from .ai_engine import find_and_save_matches_for_item

class MatchListView(generics.ListAPIView):
    serializer_class = MatchRecordSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = MatchRecord.objects.all().select_related('lost_item', 'found_item', 'lost_item__user', 'found_item__user')
        lost_id = self.request.query_params.get('lost_id')
        found_id = self.request.query_params.get('found_id')
        min_score = self.request.query_params.get('min_score')
        match_status = self.request.query_params.get('status')
        my_items = self.request.query_params.get('my_matches')

        if lost_id:
            queryset = queryset.filter(lost_item_id=lost_id)
        if found_id:
            queryset = queryset.filter(found_item_id=found_id)
        if min_score:
            try:
                queryset = queryset.filter(similarity_score__gte=float(min_score))
            except ValueError:
                pass
        if match_status:
            queryset = queryset.filter(status=match_status)
        if my_items and self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(lost_item__user=self.request.user) | Q(found_item__user=self.request.user)
            )

        return queryset


class MatchDetailView(generics.RetrieveUpdateAPIView):
    queryset = MatchRecord.objects.all().select_related('lost_item', 'found_item')
    serializer_class = MatchRecordSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class MatchGenerateView(APIView):
    """
    Triggers the AI matching engine.
    POST /api/matches/generate/
    Body options:
      { "lost_id": 12 } -> Match specific lost item against all found items
      { "found_id": 8 } -> Match specific found item against all lost items
      {} -> Trigger full cross-matching for all open items
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        lost_id = request.data.get('lost_id')
        found_id = request.data.get('found_id')
        generated_matches = []

        if lost_id:
            try:
                item = LostItem.objects.get(id=lost_id)
                opposite_qs = FoundItem.objects.filter(status__in=['open', 'matched'])
                generated_matches = find_and_save_matches_for_item(item, opposite_qs)
            except LostItem.DoesNotExist:
                return Response({"error": f"Lost item #{lost_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        elif found_id:
            try:
                item = FoundItem.objects.get(id=found_id)
                opposite_qs = LostItem.objects.filter(status__in=['open', 'matched'])
                generated_matches = find_and_save_matches_for_item(item, opposite_qs)
            except FoundItem.DoesNotExist:
                return Response({"error": f"Found item #{found_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Full cross-match
            lost_items = LostItem.objects.filter(status__in=['open', 'matched'])
            found_items = FoundItem.objects.filter(status__in=['open', 'matched'])
            for lost_item in lost_items:
                matches = find_and_save_matches_for_item(lost_item, found_items)
                generated_matches.extend(matches)

        serializer = MatchRecordSerializer(generated_matches, many=True, context={'request': request})
        return Response({
            "message": f"Matching generation completed. Processed and identified {len(generated_matches)} potential match records.",
            "count": len(generated_matches),
            "matches": serializer.data
        }, status=status.HTTP_200_OK)
