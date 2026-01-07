"""
Contact Management Models
"""
from django.db import models
from django.utils.timezone import now
from AuthN.models import BaseUserModel
from SiteManagement.models import Site


class Contact(models.Model):
    """
    Contact model to store contact details extracted from business cards or manually entered
    """
    SOURCE_CHOICES = [
        ('scanned', 'Scanned'),
        ('manual', 'Manual'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    
    # Admin and User Assignment
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_contacts',
        help_text="Admin who owns this contact"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contacts',
        help_text="Site associated with this contact"
    )
    user = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'user'},
        related_name='assigned_contacts',
        blank=True, null=True,
        help_text="User assigned to this contact (if created by user)"
    )
    
    # Basic Information
    full_name = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    job_title = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    
    # Contact Information
    mobile_number = models.CharField(max_length=20, default='')  # Required field
    alternate_phone = models.CharField(max_length=20, blank=True, null=True)
    office_landline = models.CharField(max_length=20, blank=True, null=True)
    fax_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Email Information
    email_address = models.EmailField(blank=True, null=True)
    alternate_email = models.EmailField(blank=True, null=True)
    
    # Address Information
    full_address = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    
    # Web & Social Links
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Additional Information
    additional_notes = models.TextField(blank=True, null=True)
    
    # Business Card Image
    business_card_image = models.ImageField(upload_to='business_cards/', blank=True, null=True)
    
    # Metadata
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    created_by = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE, related_name='created_contacts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Primary query optimization - most common filter patterns
            models.Index(fields=['admin', 'user', 'created_at'], name='contact_adm_user_created_idx'),
            # Status/source filtering
            models.Index(fields=['admin', 'source_type', 'created_at'], name='contact_adm_source_created_idx'),
            # Date range queries
            models.Index(fields=['admin', 'created_at'], name='contact_adm_created_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='contact_id_adm_idx'),
            # Search optimization
            models.Index(fields=['admin', 'full_name'], name='contact_adm_name_idx'),
            models.Index(fields=['admin', 'company_name'], name='contact_adm_company_idx'),
            models.Index(fields=['admin', 'mobile_number'], name='contact_adm_mobile_idx'),
            models.Index(fields=['admin', 'email_address'], name='contact_adm_email_idx'),
            models.Index(fields=['admin', 'state', 'city'], name='contact_adm_state_city_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'created_at'], name='contact_site_adm_created_idx'),
        ]
    
    def __str__(self):
        return f"{self.full_name or 'Unnamed Contact'} - {self.company_name or 'No Company'}"
