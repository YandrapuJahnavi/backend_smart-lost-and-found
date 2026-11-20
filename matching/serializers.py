from rest_framework import serializers
from .models import MatchRecord
from items.serializers import LostItemSerializer, FoundItemSerializer

class MatchRecordSerializer(serializers.ModelSerializer):
    lost_item_details = LostItemSerializer(source='lost_item', read_only=True)
    found_item_details = FoundItemSerializer(source='found_item', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MatchRecord
        fields = [
            'id', 'lost_item', 'lost_item_details', 'found_item', 'found_item_details',
            'similarity_score', 'visual_score', 'category_score', 'color_score',
            'text_score', 'location_score', 'distance_km', 'status', 'status_display',
            'breakdown', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

