from django.db import models
from django.conf import settings

class Claim(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Verification'),
        ('approved', 'Approved / Ownership Verified'),
        ('rejected', 'Rejected / Invalid Claim'),
        ('more_info_needed', 'More Proof Required'),
    )

    claimant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='claims')
    found_item = models.ForeignKey('items.FoundItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='claims')
    lost_item = models.ForeignKey('items.LostItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='claims')
    
    # Claimant contact & private proof
    claimant_name = models.CharField(max_length=150)
    claimant_phone = models.CharField(max_length=30)
    claimant_email = models.EmailField()
    
    # Sensitive identifying info (MUST NEVER be publicly exposed)
    proof_description = models.TextField(
        help_text="Detailed private identifying info: serial numbers, unique marks, wallpapers, internal contents, purchase dates, passwords/pins description."
    )
    proof_image = models.ImageField(upload_to='claims/%Y/%m/', null=True, blank=True, help_text="Purchase invoice, box photo, or older photo of the item")
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', db_index=True)
    admin_notes = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_claims'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Ownership Claim"
        verbose_name_plural = "Ownership Claims"

    def __str__(self):
        target = f"Found #{self.found_item_id}" if self.found_item_id else f"Lost #{self.lost_item_id}"
        return f"Claim #{self.id} on {target} by {self.claimant_name} ({self.get_status_display()})"
