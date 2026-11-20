from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.core.mail import send_mail
from .models import Claim
from .serializers import ClaimSerializer, ClaimStatusUpdateSerializer
from notifications.models import Notification

class IsAdminUserOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.is_staff))


class ClaimListCreateView(generics.ListCreateAPIView):
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        claim_status = self.request.query_params.get('status')
        
        # Admins see all claims, normal users only see claims they submitted
        if user.role == 'admin' or user.is_staff:
            queryset = Claim.objects.all().select_related('claimant', 'found_item', 'lost_item')
        else:
            queryset = Claim.objects.filter(claimant=user).select_related('claimant', 'found_item', 'lost_item')

        if claim_status:
            queryset = queryset.filter(status=claim_status)
        return queryset

    def perform_create(self, serializer):
        claim = serializer.save(claimant=self.request.user)

        # Notify the reporter of the found or lost item
        target_item = claim.found_item or claim.lost_item
        if target_item and target_item.user != self.request.user:
            Notification.objects.create(
                user=target_item.user,
                notification_type='claim',
                title=f"New Claim Submitted on '{target_item.title}'",
                message=f"User '{self.request.user.username}' submitted an ownership claim with identifying proof. Administrators are reviewing verification.",
                link="/claims"
            )

        # In-app notification for the claimant confirming submission
        Notification.objects.create(
            user=self.request.user,
            notification_type='claim',
            title=f"Claim Submitted Successfully (#{claim.id})",
            message=f"Your claim on '{target_item.title if target_item else 'item'}' has been received. Our team will verify proof details shortly.",
            link="/claims"
        )


class ClaimDetailView(generics.RetrieveAPIView):
    queryset = Claim.objects.all().select_related('claimant', 'found_item', 'lost_item')
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.is_staff:
            return Claim.objects.all()
        return Claim.objects.filter(claimant=user)


class ClaimStatusUpdateView(APIView):
    """
    PATCH /api/claims/{id}/status/
    Administrator action to approve, reject, or request more info on a claim.
    """
    permission_classes = [IsAdminUserOrStaff]

    def patch(self, request, pk):
        try:
            claim = Claim.objects.get(pk=pk)
        except Claim.DoesNotExist:
            return Response({"error": "Claim not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClaimStatusUpdateSerializer(claim, data=request.data, partial=True)
        if serializer.is_valid():
            new_status = serializer.validated_data.get('status', claim.status)
            claim.reviewed_by = request.user
            serializer.save()

            # If claim is approved, update target item status
            if new_status == 'approved':
                if claim.found_item:
                    claim.found_item.status = 'resolved'
                    claim.found_item.save(update_fields=['status'])
                if claim.lost_item:
                    claim.lost_item.status = 'resolved'
                    claim.lost_item.save(update_fields=['status'])

            # Send in-app notification to claimant
            Notification.objects.create(
                user=claim.claimant,
                notification_type='claim',
                title=f"Claim #{claim.id} Status: {claim.get_status_display()}",
                message=f"Your claim on item has been updated to '{claim.get_status_display()}'. Admin Notes: {claim.admin_notes or 'No additional notes.'}",
                link="/claims"
            )

            # Send email to claimant
            if claim.claimant_email:
                try:
                    send_mail(
                        subject=f"[Smart Lost & Found] Ownership Claim #{claim.id} Updated",
                        message=f"Hello {claim.claimant_name},\n\nYour claim #{claim.id} has been marked as: {claim.get_status_display()}.\n\nAdmin Remarks:\n{claim.admin_notes or 'Thank you for cooperating with verification.'}\n\nSmart Lost & Found Team",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[claim.claimant_email],
                        fail_silently=True
                    )
                except Exception:
                    pass

            return Response(ClaimSerializer(claim, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
