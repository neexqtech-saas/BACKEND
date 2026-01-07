"""
Visit Management System
Employee Visit Management with Check-in/Check-out functionality
"""

from django.db import models
from decimal import Decimal
from AuthN.models import *
from SiteManagement.models import Site


class Visit(models.Model):
    """
    Visit Management System
    Tracks employee visits to clients/locations with check-in/check-out functionality
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    
    # Admin
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_visits'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='visits',
        help_text="Site associated with this visit"
    )
    
    # Employee Assignment
    assigned_employee = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'user'},
        related_name='assigned_visits',
        help_text="Employee assigned to perform this visit"
    )
    
    # Visit Basic Details
    title = models.CharField(max_length=255, help_text="Visit title")
    description = models.TextField(blank=True, null=True, help_text="Visit description")
    schedule_date = models.DateField(help_text="Scheduled date for the visit")
    schedule_time = models.TimeField(blank=True, null=True, help_text="Scheduled time for the visit")
    
    # Client/Location Information
    client_name = models.CharField(max_length=255, blank=True, null=True, help_text="Client/Company name")
    location_name = models.CharField(max_length=255, blank=True, null=True, help_text="Location name")
    address = models.TextField(help_text="Full address of the visit location")
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True, default='India')
    
    # Contact Information
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    contact_phone = models.CharField(max_length=15, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    
    # Visit Status and Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Check-in Information (stored for quick access)
    check_in_timestamp = models.DateTimeField(null=True, blank=True)
    check_in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_note = models.TextField(blank=True, null=True)
    
    # Check-out Information (stored for quick access)
    check_out_timestamp = models.DateTimeField(null=True, blank=True)
    check_out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_note = models.TextField(blank=True, null=True)
    
    # Metadata
    created_by = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_visits',
        help_text="User who created this visit (admin or employee)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-schedule_date', '-schedule_time']
        indexes = [
            # Primary query optimization
            models.Index(fields=['admin', 'status', 'schedule_date'], name='visit_adm_status_date_idx'),
            models.Index(fields=['assigned_employee', 'status', 'schedule_date'], name='visit_emp_status_date_idx'),
            # Date range queries
            models.Index(fields=['admin', 'schedule_date'], name='visit_adm_date_idx'),
            models.Index(fields=['assigned_employee', 'schedule_date'], name='visit_emp_date_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='visit_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'status', 'schedule_date'], name='visit_site_adm_status_date_idx'),
        ]
        verbose_name = "Visit"
        verbose_name_plural = "Visits"
    
    def __str__(self):
        return f"{self.title} - {self.assigned_employee.email} ({self.schedule_date})"
    
    def can_perform_check_in_out(self, user):
        """
        Check if user can perform check-in/check-out for this visit.
        Only assigned employee or creator (if self-visit) can perform check-in/check-out.
        """
        if user.role == 'admin':
            return True  # Admins can perform check-in/check-out for any visit
        return user == self.assigned_employee or (self.created_by and user == self.created_by)
