from rest_framework import serializers
from .models import LostItem, FoundItem
from accounts.serializers import UserProfileSerializer

class LostItemSerializer(serializers.ModelSerializer):
    user_details = UserProfileSerializer(source='user', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    matches_count = serializers.SerializerMethodField()

    class Meta:
        model = LostItem
        fields = [
            'id', 'user', 'user_details', 'title', 'category', 'category_display',
            'description', 'colour', 'date_lost', 'location', 'latitude', 'longitude',
            'image', 'status', 'status_display', 'matches_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_matches_count(self, obj):
        return obj.match_records.count()


class FoundItemSerializer(serializers.ModelSerializer):
    user_details = UserProfileSerializer(source='user', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    matches_count = serializers.SerializerMethodField()

    class Meta:
        model = FoundItem
        fields = [
            'id', 'user', 'user_details', 'title', 'category', 'category_display',
            'description', 'colour', 'date_found', 'location', 'latitude', 'longitude',
            'image', 'status', 'status_display', 'matches_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_matches_count(self, obj):
        return obj.match_records.count()

