from django.db import models
from django.conf import settings

CATEGORY_CHOICES = (
    ('electronics', 'Electronics & Gadgets'),
    ('wallets', 'Wallets & Purses'),
    ('bags', 'Bags, Backpacks & Luggage'),
    ('documents', 'Documents, Cards & IDs'),
    ('keys', 'Keys & Keychains'),
    ('jewellery', 'Jewellery & Watches'),
    ('clothing', 'Clothing & Accessories'),
    ('pets', 'Pets & Animals'),
    ('others', 'Other Items'),
)

STATUS_CHOICES = (
    ('open', 'Open / Active'),
    ('matched', 'Potential Match Found'),
    ('claim_pending', 'Claim In Progress'),
    ('resolved', 'Resolved / Returned'),
    ('closed', 'Closed'),
)

class BaseItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)ss")
    title = models.CharField(max_length=200, db_index=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField()
    colour = models.CharField(max_length=60, help_text="e.g. Black, Blue, Silver", db_index=True)
    location = models.CharField(max_length=255, help_text="City, landmark, street address")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    image = models.ImageField(upload_to='items/%Y/%m/', null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open', db_index=True)
    
    # AI Embedding attributes
    image_embedding = models.JSONField(default=list, blank=True)
    embedding_model = models.CharField(max_length=64, default='none', blank=True)
    feature_extracted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"


class LostItem(BaseItem):
    date_lost = models.DateField(help_text="Date when item was lost", db_index=True)

    class Meta(BaseItem.Meta):
        verbose_name = "Lost Item"
        verbose_name_plural = "Lost Items"


class FoundItem(BaseItem):
    date_found = models.DateField(help_text="Date when item was found", db_index=True)

    class Meta(BaseItem.Meta):
        verbose_name = "Found Item"
        verbose_name_plural = "Found Items"
