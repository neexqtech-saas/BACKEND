"""
Asset Management System
Medium level asset tracking and management
"""

from django.db import models
from uuid import uuid4
from AuthN.models import BaseUserModel
from SiteManagement.models import Site


class AssetCategory(models.Model):
    """Asset Category Model"""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_asset_categories'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_categories',
        help_text="Site associated with this asset category"
    )
    
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('admin', 'code')
        ordering = ['name']
        verbose_name = 'Asset Category'
        verbose_name_plural = 'Asset Categories'
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='ac_admin_active_idx'),
            models.Index(fields=['admin', 'code'], name='ac_admin_code_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='ac_site_admin_active_idx'),
        ]
    
    def __str__(self):
        return self.name


class Asset(models.Model):
    """Asset Model"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
        ('disposed', 'Disposed'),
    ]
    
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_assets'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assets',
        help_text="Site associated with this asset"
    )
    category = models.ForeignKey(
        AssetCategory, on_delete=models.PROTECT,
        related_name='assets'
    )
    
    # Asset Identification
    asset_code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    
    # Asset Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    location = models.CharField(max_length=255, blank=True, null=True)
    
    # Financial
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    vendor = models.CharField(max_length=255, blank=True, null=True)
    
    # Additional Info
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('admin', 'asset_code')
        ordering = ['-created_at']
        indexes = [
            # Primary query optimization - most common filter pattern
            models.Index(fields=['admin', 'is_active', 'created_at'], name='asset_adm_act_created_idx'),
            # Status filtering
            models.Index(fields=['admin', 'status', 'created_at'], name='asset_adm_st_created_idx'),
            # Category filtering
            models.Index(fields=['admin', 'category', 'is_active'], name='asset_adm_cat_active_idx'),
            # Date range queries
            models.Index(fields=['admin', 'created_at'], name='asset_adm_created_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='asset_id_adm_idx'),
            # Search optimization (for asset_code, name lookups)
            models.Index(fields=['admin', 'asset_code'], name='asset_adm_code_idx'),
            models.Index(fields=['admin', 'name'], name='asset_adm_name_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active', 'created_at'], name='asset_site_adm_act_created_idx'),
        ]
    
    def __str__(self):
        return f"{self.asset_code} - {self.name}"

