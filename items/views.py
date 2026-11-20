from rest_framework import generics, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from .models import LostItem, FoundItem
from .serializers import LostItemSerializer, FoundItemSerializer
from matching.ai_engine import find_and_save_matches_for_item, calculate_haversine_distance

class IsOwnerOrAdminOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user.is_authenticated and (
                obj.user == request.user or 
                request.user.role == 'admin' or 
                request.user.is_staff
            )
        )

class LostItemListCreateView(generics.ListCreateAPIView):
    serializer_class = LostItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'colour', 'location']
    ordering_fields = ['created_at', 'date_lost', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = LostItem.objects.all().select_related('user')
        category = self.request.query_params.get('category')
        item_status = self.request.query_params.get('status')
        colour = self.request.query_params.get('colour')
        user_only = self.request.query_params.get('my_items')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if category:
            queryset = queryset.filter(category=category)
        if item_status:
            queryset = queryset.filter(status=item_status)
        if colour:
            queryset = queryset.filter(colour__icontains=colour)
        if user_only and self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        if date_from:
            queryset = queryset.filter(date_lost__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_lost__lte=date_to)

        return queryset

    def perform_create(self, serializer):
        item = serializer.save(user=self.request.user)
        # Automatically trigger AI image and attribute matching against active found items
        try:
            opposite_qs = FoundItem.objects.filter(status__in=['open', 'matched'])
            find_and_save_matches_for_item(item, opposite_qs)
        except Exception as e:
            # Matching runs gracefully without blocking item creation
            import logging
            logging.getLogger(__name__).error(f"Error in auto-matching after lost item creation: {e}")


class LostItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LostItem.objects.all().select_related('user')
    serializer_class = LostItemSerializer
    permission_classes = [IsOwnerOrAdminOrReadOnly]

    def perform_update(self, serializer):
        item = serializer.save()
        if 'image' in serializer.validated_data:
            item.feature_extracted = False
            item.image_embedding = []
            item.save()
            opposite_qs = FoundItem.objects.filter(status__in=['open', 'matched'])
            find_and_save_matches_for_item(item, opposite_qs)


class FoundItemListCreateView(generics.ListCreateAPIView):
    serializer_class = FoundItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'colour', 'location']
    ordering_fields = ['created_at', 'date_found', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = FoundItem.objects.all().select_related('user')
        category = self.request.query_params.get('category')
        item_status = self.request.query_params.get('status')
        colour = self.request.query_params.get('colour')
        user_only = self.request.query_params.get('my_items')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if category:
            queryset = queryset.filter(category=category)
        if item_status:
            queryset = queryset.filter(status=item_status)
        if colour:
            queryset = queryset.filter(colour__icontains=colour)
        if user_only and self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        if date_from:
            queryset = queryset.filter(date_found__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_found__lte=date_to)

        return queryset

    def perform_create(self, serializer):
        item = serializer.save(user=self.request.user)
        # Automatically trigger AI image and attribute matching against active lost items
        try:
            opposite_qs = LostItem.objects.filter(status__in=['open', 'matched'])
            find_and_save_matches_for_item(item, opposite_qs)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in auto-matching after found item creation: {e}")


class FoundItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FoundItem.objects.all().select_related('user')
    serializer_class = FoundItemSerializer
    permission_classes = [IsOwnerOrAdminOrReadOnly]

    def perform_update(self, serializer):
        item = serializer.save()
        if 'image' in serializer.validated_data:
            item.feature_extracted = False
            item.image_embedding = []
            item.save()
            opposite_qs = LostItem.objects.filter(status__in=['open', 'matched'])
            find_and_save_matches_for_item(item, opposite_qs)


class NearbyItemsView(APIView):
    """
    Search lost and found items within a geographic radius (km) of given coordinates.
    GET /api/items/nearby/?lat=17.385&lng=78.486&radius=25&category=electronics&type=all
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 50.0))
        item_type = request.query_params.get('type', 'all')
        category = request.query_params.get('category')

        if not lat or not lng:
            return Response(
                {"error": "Latitude ('lat') and Longitude ('lng') parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            center_lat = float(lat)
            center_lng = float(lng)
        except ValueError:
            return Response({"error": "Invalid coordinates provided."}, status=status.HTTP_400_BAD_REQUEST)

        results = []

        # Process Lost Items
        if item_type in ('all', 'lost'):
            lost_qs = LostItem.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
            if category:
                lost_qs = lost_qs.filter(category=category)
            
            for item in lost_qs:
                try:
                    d = calculate_haversine_distance(center_lat, center_lng, float(item.latitude), float(item.longitude))
                    if d <= radius:
                        data = LostItemSerializer(item, context={'request': request}).data
                        data['type'] = 'lost'
                        data['distance_km'] = d
                        results.append(data)
                except Exception:
                    continue

        # Process Found Items
        if item_type in ('all', 'found'):
            found_qs = FoundItem.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
            if category:
                found_qs = found_qs.filter(category=category)

            for item in found_qs:
                try:
                    d = calculate_haversine_distance(center_lat, center_lng, float(item.latitude), float(item.longitude))
                    if d <= radius:
                        data = FoundItemSerializer(item, context={'request': request}).data
                        data['type'] = 'found'
                        data['distance_km'] = d
                        results.append(data)
                except Exception:
                    continue

        # Sort by proximity
        results.sort(key=lambda x: x['distance_km'])
        return Response({
            "center": {"lat": center_lat, "lng": center_lng},
            "radius_km": radius,
            "count": len(results),
            "results": results
        })
