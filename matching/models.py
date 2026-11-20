from django.db import models

class MatchRecord(models.Model):
    STATUS_CHOICES = (
        ('potential', 'Potential Match'),
        ('confirmed', 'Confirmed by Users/Admin'),
        ('rejected', 'Rejected / False Match'),
        ('investigating', 'Under Investigation'),
    )

    lost_item = models.ForeignKey('items.LostItem', on_delete=models.CASCADE, related_name='match_records')
    found_item = models.ForeignKey('items.FoundItem', on_delete=models.CASCADE, related_name='match_records')
    
    # Scores are stored as percentages 0.0 - 100.0
    similarity_score = models.FloatField(db_index=True, help_text="Total weighted match percentage")
    visual_score = models.FloatField(default=0.0, help_text="Visual cosine similarity percentage")
    category_score = models.FloatField(default=0.0, help_text="Category similarity percentage")
    color_score = models.FloatField(default=0.0, help_text="Colour matching score")
    text_score = models.FloatField(default=0.0, help_text="Title and description overlap")
    location_score = models.FloatField(default=0.0, help_text="Geographical proximity score")
    distance_km = models.FloatField(null=True, blank=True, help_text="Approx distance in km")

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='potential', db_index=True)
    breakdown = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-similarity_score', '-created_at']
        unique_together = ('lost_item', 'found_item')
        verbose_name = "Match Record"
        verbose_name_plural = "Match Records"

    def __str__(self):
        return f"Match #{self.id}: Lost #{self.lost_item_id} <-> Found #{self.found_item_id} ({self.similarity_score:.1f}%)"
