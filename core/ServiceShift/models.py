from django.db import models
import uuid
from AuthN.models import *
from datetime import datetime, timedelta , time
from AuthN.models import *  # Import your custom BaseUserModel
from SiteManagement.models import Site


class ServiceShift(models.Model):
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'admin'}, related_name="admin_shift")
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='shifts',
        help_text="Site associated with this shift"
    )
    shift_name = models.CharField(max_length=255, null=True, blank=True, default="Default Shift")
    start_time = models.TimeField(default=time(9, 0))
    end_time = models.TimeField(default=time(9, 0))
    break_duration_minutes = models.IntegerField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    is_night_shift = models.BooleanField(default=False, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['shift_name']
        indexes = [
            models.Index(fields=['admin', 'is_active'], name='shift_adm_active_idx'),
            models.Index(fields=['id', 'admin'], name='shift_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active'], name='shift_site_adm_active_idx'),
        ]

    def save(self, *args, **kwargs):
        # Calculate total duration in minutes (accounting for night shift logic)
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = datetime.combine(datetime.today(), self.end_time)

        # Handle night shift where end_time is past midnight
        if self.end_time <= self.start_time:
            end_dt += timedelta(days=1)
            self.is_night_shift = True
        else:
            self.is_night_shift = False

        total_minutes = int((end_dt - start_dt).total_seconds() / 60)

        # Subtract break if provided
        break_minutes = self.break_duration_minutes if self.break_duration_minutes else 0
        self.duration_minutes = total_minutes - break_minutes

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shift_name or 'Shift'} ({self.start_time} - {self.end_time})"

# class UserShiftAssignment(models.Model):
#     id = models.BigAutoField(primary_key=True)  # Auto-incrementing BigInt ID
#     user = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE)
#     shift = models.ForeignKey(ServiceShift, on_delete=models.CASCADE)
#     admin = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE)
#     organization = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE)
#     attendance_date = models.DateField()
#     assignment_type = models.CharField(max_length=50, default='Auto')
#     assigned_by = models.UUIDField(null=True, blank=True)
#     assignment_time = models.DateTimeField(null=True, blank=True)
#     remarks = models.TextField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)