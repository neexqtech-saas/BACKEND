from django.db import models
from AuthN.models import *
from SiteManagement.models import Site

# Create your models here.
class Holiday(models.Model):
    id = models.BigAutoField(primary_key=True)  # Auto-incrementing BigInt ID
    admin = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE , limit_choices_to={'role': 'admin'}, related_name="admin_holiday")
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='holidays',
        help_text="Site associated with this holiday"
    )
    organization = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'organization'},related_name="organization_holiday")
    name = models.CharField(max_length=255)
    holiday_date = models.DateField()
    is_optional = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-holiday_date']
        indexes = [
            models.Index(fields=['admin', 'is_active', 'holiday_date'], name='holiday_adm_active_date_idx'),
            models.Index(fields=['organization', 'is_active', 'holiday_date'], name='holiday_org_active_date_idx'),
            models.Index(fields=['admin', 'holiday_date'], name='holiday_adm_date_idx'),
            models.Index(fields=['id', 'admin'], name='holiday_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active', 'holiday_date'], name='holiday_site_adm_act_dt_idx'),
        ]

    def __str__(self):
        return self.name

