from rest_framework import serializers
from .models import Claim
from items.serializers import LostItemSerializer, FoundItemSerializer

class ClaimSerializer(serializers.ModelSerializer):
    claimant_username = serializers.CharField(source='claimant.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lost_item_details = LostItemSerializer(source='lost_item', read_only=True)
    found_item_details = FoundItemSerializer(source='found_item', read_only=True)

    class Meta:
        model = Claim
        fields = [
            'id', 'claimant', 'claimant_username', 'found_item', 'found_item_details',
            'lost_item', 'lost_item_details', 'claimant_name', 'claimant_phone',
            'claimant_email', 'proof_description', 'proof_image', 'status', 'status_display',
            'admin_notes', 'reviewed_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'claimant', 'status', 'reviewed_by', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """
        SECURITY REQUIREMENT:
        Never publicly expose sensitive identifying information.
        Only the claimant and administrators can view proof_description and proof_image.
        """
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        is_owner = request and request.user.is_authenticated and instance.claimant_id == request.user.id
        is_admin = request and request.user.is_authenticated and (request.user.role == 'admin' or request.user.is_staff)

        if not (is_owner or is_admin):
            data['proof_description'] = "[RESTRICTED - VERIFICATION CONFIDENTIAL TO CLAIMANT & ADMINS]"
            data['proof_image'] = None
            data['claimant_phone'] = "[RESTRICTED]"
            data['claimant_email'] = "[RESTRICTED]"

        return data


class ClaimStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = ['status', 'admin_notes']

