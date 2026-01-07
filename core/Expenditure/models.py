"""
Advanced Expense Management System for India
Comprehensive expense tracking, approval, reimbursement, and tax compliance
"""

from django.db import models
from decimal import Decimal
from datetime import date, datetime
from AuthN.models import *
from SiteManagement.models import Site


class ExpenseCategory(models.Model):
    """Expense Category - Extended"""
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name="admin_expense_categories"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expense_categories',
        help_text="Site associated with this expense category"
    )
    name = models.CharField(max_length=255, default="Service Expense")
    description = models.TextField(blank=True, null=True)
    code = models.CharField(max_length=50, blank=True, null=True)
    
    # Tax Settings
    is_taxable = models.BooleanField(default=True)
    gst_applicable = models.BooleanField(default=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00, help_text="GST %")
    tds_applicable = models.BooleanField(default=False)
    tds_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="TDS %")
    
    # Limits
    max_amount_per_transaction = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_amount_per_month = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    requires_approval = models.BooleanField(default=True)
    requires_receipt = models.BooleanField(default=True)
    
    # Budget
    monthly_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    color_code = models.CharField(max_length=7, default='#3498db')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('admin', 'code') if 'code' else None
        ordering = ['name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='expcat_adm_active_idx'),
            models.Index(fields=['id', 'admin'], name='expcat_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='expcat_site_adm_active_idx'),
        ]
    
    def __str__(self):
        return self.name


class ExpenseProject(models.Model):
    """Expense Project - Similar to ExpenseCategory"""
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name="admin_expense_projects"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expense_projects',
        help_text="Site associated with this expense project"
    )
    name = models.CharField(max_length=255, default="Project")
    description = models.TextField(blank=True, null=True)
    code = models.CharField(max_length=50, blank=True, null=True)
    
    color_code = models.CharField(max_length=7, default='#3498db')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('admin', 'code') if 'code' else None
        ordering = ['name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='expproj_adm_active_idx'),
            models.Index(fields=['id', 'admin'], name='expproj_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='expproj_site_adm_active_idx'),
        ]
    
    def __str__(self):
        return self.name


class Expense(models.Model):
    """Expense Model - Advanced"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]
    
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('cheque', 'Cheque'),
        ('neft', 'NEFT'),
        ('rtgs', 'RTGS'),
        ('other', 'Other')
    ]
    
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_expenses'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expenses',
        help_text="Site associated with this expense"
    )
    employee = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'user'},
        related_name='employee_expenses'
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT,
        related_name='expenses'
    )
    project = models.ForeignKey(
        ExpenseProject, on_delete=models.PROTECT,
        related_name='expenses',
        null=True, blank=True  # Temporarily nullable for migration, will be made required after data migration
    )
    
    # Expense Details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    expense_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    
    # Status & Approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_expenses',
        limit_choices_to={'role__in': ['admin', 'user']}
    )
    rejection_reason = models.TextField(blank=True, null=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rejected_expenses'
    )
    
    # Reimbursement
    reimbursement_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    reimbursement_date = models.DateField(null=True, blank=True)
    reimbursement_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, blank=True, null=True)
    reimbursement_reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Documents
    receipts = models.JSONField(default=list, blank=True, help_text="List of receipt file paths")
    supporting_documents = models.JSONField(default=list, blank=True)
    
    # Additional
    remarks = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_expenses'
    )
    
    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [
            # Primary query optimization
            models.Index(fields=['admin', 'status', 'expense_date'], name='expense_adm_status_date_idx'),
            models.Index(fields=['employee', 'status', 'expense_date'], name='expense_emp_status_date_idx'),
            # Date range queries
            models.Index(fields=['admin', 'expense_date'], name='expense_adm_date_idx'),
            models.Index(fields=['employee', 'expense_date'], name='expense_emp_date_idx'),
            # Category filtering
            models.Index(fields=['admin', 'category', 'status'], name='expense_adm_cat_status_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='expense_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'status', 'expense_date'], name='expense_site_adm_st_dt_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.employee.email} - ₹{self.amount}"
