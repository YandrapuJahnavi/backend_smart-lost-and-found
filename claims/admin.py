from django.contrib import admin
from .models import Claim

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('id', 'claimant', 'found_item', 'lost_item', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'created_at')
    search_fields = ('claimant__username', 'claimant_name', 'claimant_email', 'proof_description')
    readonly_fields = ('created_at', 'updated_at')
