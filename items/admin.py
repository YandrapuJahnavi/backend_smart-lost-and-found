from django.contrib import admin
from .models import LostItem, FoundItem

@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'colour', 'location', 'date_lost', 'user', 'status', 'created_at')
    list_filter = ('category', 'status', 'date_lost', 'created_at')
    search_fields = ('title', 'description', 'colour', 'location', 'user__username')
    readonly_fields = ('feature_extracted', 'embedding_model', 'created_at', 'updated_at')


@admin.register(FoundItem)
class FoundItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'colour', 'location', 'date_found', 'user', 'status', 'created_at')
    list_filter = ('category', 'status', 'date_found', 'created_at')
    search_fields = ('title', 'description', 'colour', 'location', 'user__username')
    readonly_fields = ('feature_extracted', 'embedding_model', 'created_at', 'updated_at')
