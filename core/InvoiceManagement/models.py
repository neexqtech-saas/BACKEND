"""
Invoice Management System
Comprehensive invoice creation and management for admin users
"""

from django.db import models
from decimal import Decimal
from datetime import date
from AuthN.models import BaseUserModel
from SiteManagement.models import Site


class Invoice(models.Model):
    """Invoice Model"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled')
    ]
    
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_invoices'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
        help_text="Site associated with this invoice"
    )
    
    # Invoice Details
    invoice_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    theme_color = models.CharField(max_length=20, default='red')
    
    # Business Details (From)
    business_name = models.CharField(max_length=255)
    business_contact_name = models.CharField(max_length=255, blank=True, null=True)
    business_gstin = models.CharField(max_length=15, blank=True, null=True)
    business_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    business_city = models.CharField(max_length=100, blank=True, null=True)
    business_state = models.CharField(max_length=100, blank=True, null=True)
    business_country = models.CharField(max_length=100, default='India')
    business_pincode = models.CharField(max_length=10, blank=True, null=True)
    business_logo = models.ImageField(upload_to='invoice_logos/', blank=True, null=True)
    
    # Client Details (To)
    client_name = models.CharField(max_length=255)
    client_gstin = models.CharField(max_length=15, blank=True, null=True)
    client_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    client_city = models.CharField(max_length=100, blank=True, null=True)
    client_state = models.CharField(max_length=100, blank=True, null=True)
    client_country = models.CharField(max_length=100, default='India')
    client_pincode = models.CharField(max_length=10, blank=True, null=True)
    
    # Place of Supply
    place_of_supply = models.CharField(max_length=100, blank=True, null=True)
    
    # Totals
    sub_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_sgst = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_cgst = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_cess = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Details
    notes = models.TextField(blank=True, null=True)
    terms_and_conditions = models.TextField(blank=True, null=True)
    
    # Items stored as JSON array
    items = models.JSONField(default=list, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Primary query optimization - most common filter patterns
            models.Index(fields=['admin', 'status'], name='invoice_adm_status_idx'),
            models.Index(fields=['admin', 'invoice_date'], name='invoice_adm_date_idx'),
            # Invoice number lookup - unique constraint already creates index, but explicit for clarity
            models.Index(fields=['invoice_number'], name='invoice_number_idx'),
            # Date range queries
            models.Index(fields=['invoice_date'], name='invoice_date_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='invoice_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'status', 'invoice_date'], name='invoice_site_adm_st_dt_idx'),
            # Search optimization
            models.Index(fields=['admin', 'client_name'], name='invoice_adm_client_name_idx'),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number or self.id} - {self.client_name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate invoice number if not provided
            last_invoice = Invoice.objects.filter(admin=self.admin).order_by('-created_at').first()
            if last_invoice and last_invoice.invoice_number:
                try:
                    last_num = int(last_invoice.invoice_number.split('-')[-1])
                    self.invoice_number = f"INV-{str(self.admin.id)[:8].upper()}-{last_num + 1:05d}"
                except:
                    self.invoice_number = f"INV-{str(self.admin.id)[:8].upper()}-00001"
            else:
                self.invoice_number = f"INV-{str(self.admin.id)[:8].upper()}-00001"
        super().save(*args, **kwargs)



