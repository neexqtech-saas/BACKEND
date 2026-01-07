"""
Advanced Task Management System
Comprehensive task tracking, assignments, and project management
"""

from django.db import models
from datetime import date, datetime
from AuthN.models import *
from SiteManagement.models import Site


class TaskType(models.Model):
    """Task Type Master"""
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name="admin_task_type"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='task_types',
        help_text="Site associated with this task type"
    )
    name = models.CharField(max_length=255, null=True, blank=True, default="Service Task")
    description = models.TextField(blank=True, null=True)
    color_code = models.CharField(max_length=7, default='#3498db')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='tasktype_adm_active_idx'),
            models.Index(fields=['id', 'admin'], name='tasktype_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='tasktype_site_adm_active_idx'),
        ]
    
    def __str__(self):
        return self.name


class Task(models.Model):
    """Task Model - Extended"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ]
    
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_tasks'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tasks',
        help_text="Site associated with this task"
    )
    task_type = models.ForeignKey(
        TaskType, on_delete=models.PROTECT,
        related_name='tasks'
    )
    
    # Task Details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Assignment
    assigned_to = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'user'},
        related_name='assigned_tasks'
    )
    assigned_by = models.ForeignKey(
        BaseUserModel, on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'admin'},
        related_name='created_tasks'
    )
    
    # Timeline
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Scheduling
    schedule_frequency = models.CharField(
        max_length=20,
        choices=[
            ('onetime', 'One Time'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly')
        ],
        default='onetime'
    )
    week_day = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Day of week for weekly schedule (0=Monday, 6=Sunday)"
    )
    month_date = models.IntegerField(
        blank=True,
        null=True,
        help_text="Date of month for monthly schedule (1-31)"
    )
    schedule_end_date = models.DateField(
        blank=True,
        null=True,
        help_text="End date for recurring schedules"
    )
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='scheduled_instances',
        help_text="Parent task for scheduled instances"
    )
    is_scheduled_instance = models.BooleanField(
        default=False,
        help_text="True if this task was created by scheduler"
    )
    
    # Recurrence (deprecated - keeping for backward compatibility)
    is_recurring = models.BooleanField(default=False)
    recurrence_frequency = models.CharField(
        max_length=50,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly')
        ],
        blank=True, null=True
    )
    recurrence_end_date = models.DateField(blank=True, null=True)
    
    # Additional
    tags = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    dependencies = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependent_tasks'
    )
    
    # Progress
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    checklist = models.JSONField(default=list, blank=True)
    
    # Comments & Notes
    comments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Primary query optimization
            models.Index(fields=['admin', 'status', 'created_at'], name='task_adm_status_created_idx'),
            models.Index(fields=['assigned_to', 'status', 'created_at'], name='task_assigned_st_created_idx'),
            # Date range queries
            models.Index(fields=['admin', 'due_date', 'status'], name='task_adm_due_status_idx'),
            models.Index(fields=['assigned_to', 'due_date', 'status'], name='task_assigned_due_status_idx'),
            # Schedule queries
            models.Index(fields=['schedule_frequency', 'is_scheduled_instance'], name='task_schedule_idx'),
            models.Index(fields=['parent_task'], name='task_parent_idx'),
            models.Index(fields=['week_day'], name='task_weekday_idx'),
            models.Index(fields=['month_date'], name='task_monthdate_idx'),
            # Detail view optimization
            models.Index(fields=['id', 'admin'], name='task_id_adm_idx'),
        ]
    
    def __str__(self):
        return self.title

class TaskComment(models.Model):
    """Task Comments"""
    id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='task_comments'
    )
    admin = models.ForeignKey(
        BaseUserModel, on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='task_comments'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='task_comments',
        help_text="Site associated with this task comment"
    )
    comment = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    is_internal = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'created_at'], name='taskcomment_task_created_idx'),
            models.Index(fields=['admin', 'created_at'], name='taskcomment_adm_created_idx'),
        ]
    
    def __str__(self):
        return f"Comment on {self.task.title}"

