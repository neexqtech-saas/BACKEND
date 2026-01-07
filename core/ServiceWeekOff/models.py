from django.db import models
from AuthN.models import *  # Import your custom BaseUserModel
from SiteManagement.models import Site

# Create your models here.
class WeekOffPolicy(models.Model):
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE,limit_choices_to={'role': 'admin'}, related_name="admin_week_off")
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='week_off_policies',
        help_text="Site associated with this week off policy"
    )
    name = models.CharField(max_length=255, default="Default Week Off")
    week_off_type = models.CharField(max_length=100, help_text="e.g. Fixed, Rotational, Alternate", default="Default")
    
    # Comma-separated or JSON list of days e.g. ["Monday", "Friday"]
    def default_week_days():
        return ["Sunday"]
    week_days = models.JSONField(help_text="List of weekdays off", default=default_week_days)
    
    # Week off cycle like [1, 2, 3, 4, 5] for repeating weeks in a month
    def default_week_off_cycle():
        return [1, 2, 3, 4, 5]
    week_off_cycle = models.JSONField(default=default_week_off_cycle)

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='weekoff_adm_active_idx'),
            models.Index(fields=['id', 'admin'], name='weekoff_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='weekoff_site_adm_active_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.admin_id})"


# class UserCustomWeekOff(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     user = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE)
#     admin = models.ForeignKey(AdminProfile, on_delete=models.CASCADE)
#     organization = models.ForeignKey(OrganizationProfile, on_delete=models.CASCADE)
#     week_off_date = models.DateField()
#     reason = models.CharField(max_length=255, null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
