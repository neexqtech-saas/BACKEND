from django.db import models
import uuid
from AuthN.models import BaseUserModel  # Adjust if your base user import is different
from SiteManagement.models import Site

class Location(models.Model):
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE,limit_choices_to={'role': 'admin'},related_name='locations_created')
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='locations',
        help_text="Site associated with this location"
    )
    organization = models.ForeignKey(BaseUserModel,on_delete=models.CASCADE,limit_choices_to={'role': 'organization'},related_name='organization_locations')
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius = models.IntegerField(help_text="Radius in meters for geofencing", default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='location_adm_active_idx'),
            models.Index(fields=['organization', 'is_active'], name='location_org_active_idx'),
            models.Index(fields=['id', 'admin'], name='location_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='location_site_adm_active_idx'),
        ]

    def __str__(self):
        return self.name

