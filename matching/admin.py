from django.contrib import admin
from .models import MatchRecord

@admin.register(MatchRecord)
class MatchRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'lost_item', 'found_item', 'similarity_score', 'visual_score', 'distance_km', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('lost_item__title', 'found_item__title', 'notes')
    readonly_fields = ('created_at', 'updated_at')
