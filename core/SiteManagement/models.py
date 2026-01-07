"""
Site Management Models
Handles Site creation and Employee-Admin-Site assignments with date-based tracking
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from uuid import uuid4
from AuthN.models import BaseUserModel


class Site(models.Model):
    """
    Site model - Sites belong to Organizations and are created by Admins
    Only Admins can create sites under their organization
    """
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    organization = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'organization'},
        related_name='organization_sites',
        help_text="Organization this site belongs to"
    )
    created_by_admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='created_sites',
        help_text="Admin who created this site"
    )
    site_name = models.CharField(max_length=255, help_text="Name of the site")
    address = models.TextField(help_text="Full address of the site")
    city = models.CharField(max_length=100, help_text="City")
    state = models.CharField(max_length=100, help_text="State")
    pincode = models.CharField(max_length=10, blank=True, null=True, help_text="Pincode/ZIP code")
    contact_person = models.CharField(max_length=255, blank=True, null=True, help_text="Contact person at site")
    contact_number = models.CharField(max_length=20, blank=True, null=True, help_text="Contact number")
    description = models.TextField(blank=True, null=True, help_text="Additional description/notes about the site")
    is_active = models.BooleanField(default=True, help_text="Whether the site is active")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['site_name']
        indexes = [
            models.Index(fields=['organization', 'is_active'], name='site_org_active_idx'),
            models.Index(fields=['created_by_admin', 'is_active'], name='site_admin_active_idx'),
            models.Index(fields=['id', 'created_by_admin'], name='site_id_admin_idx'),
        ]
    
    def __str__(self):
        return f"{self.site_name} ({self.city}, {self.state})"
    
    def clean(self):
        """Validate that admin belongs to the organization"""
        if self.created_by_admin and self.organization:
            admin_profile = self.created_by_admin.own_admin_profile
            if admin_profile and admin_profile.organization != self.organization:
                raise ValidationError("Admin must belong to the specified organization")
    
    def save(self, *args, **kwargs):
        """Override save to ensure admin belongs to organization"""
        self.full_clean()
        super().save(*args, **kwargs)


class EmployeeAdminSiteAssignment(models.Model):
    """
    Tracks employee assignments to admin-site combinations with date ranges.
    Supports multiple admins per employee within the same month.
    
    HISTORY MANAGEMENT:
    - Multiple entries are allowed for the same employee (for history tracking)
    - Only ONE assignment can be active (is_active=True) at a time
    - When a new assignment is created, previous active assignments are deactivated
    - Deactivated assignments are NOT deleted - they serve as historical records
    - Use end_date to track when an assignment ended
    - This allows tracking: "Which site was this employee assigned to in the past?"
    """
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'user'},
        related_name='admin_site_assignments',
        help_text="Employee assigned"
    )
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='employee_assignments',
        help_text="Admin under whom employee is assigned"
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_assignments',
        help_text="Site where employee is assigned (optional)"
    )
    start_date = models.DateField(help_text="Assignment start date")
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Assignment end date (NULL for active assignments)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this assignment is currently active"
    )
    assigned_by = models.ForeignKey(
        BaseUserModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role__in': ['admin', 'organization']},
        related_name='created_assignments',
        help_text="User who created this assignment"
    )
    assignment_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for assignment/transfer"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['employee', '-start_date']
        indexes = [
            models.Index(fields=['employee', 'start_date', 'end_date'], name='assignment_emp_dates_idx'),
            models.Index(fields=['admin', 'is_active'], name='assignment_admin_active_idx'),
            models.Index(fields=['site', 'start_date', 'end_date'], name='assignment_site_dates_idx'),
            models.Index(fields=['employee', 'admin'], name='assignment_emp_admin_idx'),
            models.Index(fields=['employee', 'is_active'], name='assignment_emp_active_idx'),
        ]
    
    def __str__(self):
        site_name = self.site.site_name if self.site else "No Site"
        return f"{self.employee.email} -> {self.admin.email} @ {site_name} ({self.start_date} to {self.end_date or 'Active'})"
    
    def clean(self):
        """
        Validate date ranges and ensure only one active assignment per employee.
        Multiple entries are allowed for history tracking, but only one can be active.
         
        Note: Same date entries are allowed:
        - One entry can end on date X (end_date = X)
        - Another entry can start on date X (start_date = X)
        This allows tracking transfers that happen on the same day.
        """
        if self.end_date and self.start_date:
            if self.end_date < self.start_date:
                raise ValidationError("End date cannot be before start date")
            # Allow end_date == start_date for same-day transfers
        
        # Allow multiple active assignments per employee
        # This enables tracking employees working under multiple admins/sites simultaneously
        # No validation needed - multiple active assignments are allowed
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def end_assignment(self, end_date=None, reason=None):
        """
        Helper method to end an assignment.
        This preserves the assignment as a historical record (does not delete it).
        """
        if end_date is None:
            end_date = timezone.now().date()
        
        if self.end_date and self.end_date < end_date:
            raise ValidationError("Cannot set end_date to a date after existing end_date")
        
        self.end_date = end_date
        self.is_active = False
        if reason:
            self.assignment_reason = reason
        self.save()
    
    @classmethod
    def get_assignment_history(cls, employee_id, admin_id=None):
        """
        Get complete assignment history for an employee.
        
        Args:
            employee_id: UUID of the employee
            admin_id: Optional UUID of admin to filter by
        
        Returns:
            QuerySet of all assignments (active and historical) ordered by start_date descending
        """
        filter_kwargs = {'employee_id': employee_id}
        if admin_id:
            filter_kwargs['admin_id'] = admin_id
        
        return cls.objects.filter(**filter_kwargs).select_related(
            'employee', 'admin', 'site', 'assigned_by'
        ).order_by('-start_date', '-created_at')
    
    @classmethod
    def get_active_assignment(cls, employee_id, admin_id=None):
        """
        Get current active assignment for an employee.
        
        Args:
            employee_id: UUID of the employee
            admin_id: Optional UUID of admin to filter by
        
        Returns:
            EmployeeAdminSiteAssignment or None
        """
        filter_kwargs = {
            'employee_id': employee_id,
            'is_active': True
        }
        if admin_id:
            filter_kwargs['admin_id'] = admin_id
        
        return cls.objects.filter(**filter_kwargs).select_related(
            'employee', 'admin', 'site', 'assigned_by'
        ).order_by('-start_date').first()

