"""
Simple Leave Management System
"""

from django.db import models
from datetime import datetime
from decimal import Decimal
from AuthN.models import *
from SiteManagement.models import Site


# ==================== LEAVE TYPE ====================
class LeaveType(models.Model):
    """Leave Type Master"""
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_leave_types'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leave_types',
        help_text="Site associated with this leave type"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)  # CL, SL, EL, PL, ML, etc.
    description = models.TextField(blank=True, null=True)
    
    # Leave Settings
    default_count = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('admin', 'code', 'is_active')
        ordering = ['name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='leavetype_adm_active_idx'),
            models.Index(fields=['id', 'admin'], name='leavetype_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='leavetype_site_adm_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


# ==================== EMPLOYEE LEAVE BALANCE ====================
class EmployeeLeaveBalance(models.Model):
    """Employee Leave Balance - One user can have multiple leave types"""
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'user'},
        related_name='leave_balances'
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='employee_balances')
    year = models.PositiveIntegerField()
    
    # Balance Details
    assigned = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    used = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'leave_type', 'year')
        ordering = ['-year', 'leave_type__name']
        indexes = [
            models.Index(fields=['user', 'year'], name='leavebal_user_year_idx'),
            models.Index(fields=['leave_type', 'year'], name='leavebal_type_year_idx'),
            models.Index(fields=['user', 'leave_type', 'year'], name='leavebal_user_type_year_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'user'], name='leavebal_id_user_idx'),
        ]
    
    @property
    def balance(self):
        """Current balance - Returns Decimal"""
        assigned = self.assigned if isinstance(self.assigned, Decimal) else Decimal(str(self.assigned))
        used = self.used if isinstance(self.used, Decimal) else Decimal(str(self.used))
        return assigned - used
    
    def __str__(self):
        return f"{self.user.email} - {self.leave_type.code} ({self.year}): {self.balance} days"


# ==================== LEAVE APPLICATION ====================
class LeaveApplication(models.Model):
    """Leave Application"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    LEAVE_DAY_CHOICES = [
        ('full_day', 'Full Day'),
        ('first_half', 'First Half Day'),
        ('second_half', 'Second Half Day'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_leave_applications'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leave_applications',
        help_text="Site associated with this leave application"
    )
    organization = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'organization'},
        related_name='org_leave_applications'
    )
    user = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'user'},
        related_name='user_leave_applications'
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name='applications')
    
    # Leave Details
    from_date = models.DateField()
    to_date = models.DateField()
    total_days = models.DecimalField(max_digits=5, decimal_places=2)
    leave_day_type = models.CharField(max_length=20, choices=LEAVE_DAY_CHOICES)
    reason = models.TextField()
    
    # Status & Approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_leaves'
    )
    comments = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-applied_at']
        indexes = [
            # Primary query optimization
            models.Index(fields=['admin', 'status', 'applied_at'], name='leaveapp_adm_st_app_idx'),
            models.Index(fields=['user', 'status', 'applied_at'], name='leaveapp_user_st_app_idx'),
            models.Index(fields=['organization', 'status', 'applied_at'], name='leaveapp_org_st_app_idx'),
            # Date range queries
            models.Index(fields=['user', 'from_date', 'to_date'], name='leaveapp_user_dates_idx'),
            models.Index(fields=['admin', 'from_date', 'to_date'], name='leaveapp_adm_dates_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='leaveapp_id_adm_idx'),
            models.Index(fields=['id', 'user'], name='leaveapp_id_user_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'status', 'applied_at'], name='leaveapp_site_adm_st_app_idx'),
            # Overlapping leave check optimization
            models.Index(fields=['user', 'from_date', 'to_date', 'status'], name='leaveapp_user_dates_status_idx'),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.leave_type.code} ({self.from_date} to {self.to_date})"
