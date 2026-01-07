# serializers.py
from rest_framework import serializers
from .models import Attendance
from datetime import datetime, date
from django.utils import timezone

# Get UTC timezone - compatible with all Django versions
try:
    import pytz
    UTC = pytz.UTC
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        UTC = ZoneInfo("UTC")
    except ImportError:
        # Fallback to datetime.timezone.utc (Python 3.2+)
        from datetime import timezone as dt_timezone
        UTC = dt_timezone.utc

from utils.Attendance.attendance_utils import *
from utils.helpers.image_utils import save_multiple_base64_images
class AttendanceSerializer(serializers.ModelSerializer):
    # Custom field to accept base64 images from frontend (can be single string or list)
    base64_images = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True,
        help_text="Base64 encoded image string (single image)"
    )
    
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_working_seconds', 'overtime_minutes']

    def validate(self, data):
        if not data.get('check_in_time') and not data.get('check_out_time'):
            raise serializers.ValidationError("At least check_in_time or check_out_time is required.")
        return data
    
    def create(self, validated_data):
        # Extract base64_images if present and normalize to list
        base64_images = validated_data.pop('base64_images', None)
        if base64_images and isinstance(base64_images, str):
            base64_images = [base64_images]
        
        # Determine image type based on check_in_time (if check_in_time exists, it's check-in)
        image_type = 'check_in' if validated_data.get('check_in_time') else 'check_out'
        captured_at = validated_data.get('check_in_time') or validated_data.get('check_out_time')
        
        # Create attendance instance
        attendance = super().create(validated_data)
        
        # Image processing removed - images are no longer stored
        return attendance
    
    def update(self, instance, validated_data):
        # Extract base64_images if present and normalize to list
        base64_images = validated_data.pop('base64_images', None)
        if base64_images and isinstance(base64_images, str):
            base64_images = [base64_images]
        
        # Determine image type based on what's being updated
        image_type = 'check_out'
        captured_at = None
        
        if 'check_in_time' in validated_data:
            image_type = 'check_in'
            captured_at = validated_data.get('check_in_time')
        elif 'check_out_time' in validated_data:
            image_type = 'check_out'
            captured_at = validated_data.get('check_out_time')
        else:
            # Default to check_out if neither is being updated
            image_type = 'check_out'
            captured_at = instance.check_out_time or timezone.now()
        
        # Update attendance instance
        attendance = super().update(instance, validated_data)
        
        # Image processing removed - images are no longer stored
        return attendance


class AttendanceOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    user_id = serializers.CharField(allow_null=True)  # Add user_id UUID
    employee_name = serializers.CharField()
    employee_id = serializers.CharField()
    custom_employee_id = serializers.CharField()  # Add custom_employee_id
    employee_email = serializers.CharField()
    attendance_status = serializers.CharField()
    last_login_status = serializers.CharField(allow_null=True)
    check_in = serializers.CharField(allow_null=True)
    check_out = serializers.CharField(allow_null=True)
    break_duration = serializers.CharField()
    late_minutes_display = serializers.CharField()
    production_hours = serializers.CharField()
    attendance_date = serializers.CharField()
    shift_name = serializers.CharField()
    is_late = serializers.BooleanField()
    late_minutes = serializers.IntegerField()
    is_early_exit = serializers.BooleanField()
    early_exit_minutes = serializers.IntegerField()
    multiple_entries = serializers.ListField()
    remarks = serializers.CharField(allow_null=True)
    


class EditAttendanceSerializer(serializers.ModelSerializer):
    # Custom field to accept base64 images from frontend (can be single string or list)
    base64_images = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True,
        help_text="Base64 encoded image string (single image) or list of base64 strings"
    )
    
    def to_internal_value(self, data):
        # Convert single string to list if needed
        if 'base64_images' in data:
            if isinstance(data['base64_images'], str):
                data = data.copy()
                data['base64_images'] = [data['base64_images']]
        return super().to_internal_value(data)
    
    class Meta:
        model = Attendance
        fields = ["check_in_time", "check_out_time", "remarks", "base64_images"]

    def validate_check_in_time(self, value):
        """Ensure check_in_time is timezone-aware"""
        # Middleware already converts to UTC and returns ISO string with 'Z'
        # DRF DateTimeField parses it correctly as UTC
        # Only handle if somehow still naive (fallback - should not happen)
        if value and timezone.is_naive(value):
            value = timezone.make_aware(value, UTC)
        # If already aware, return as-is (middleware ensures it's UTC)
        return value
    
    def validate_check_out_time(self, value):
        """Ensure check_out_time is timezone-aware"""
        # Middleware already converts to UTC and returns ISO string with 'Z'
        # DRF DateTimeField parses it correctly as UTC
        # Only handle if somehow still naive (fallback - should not happen)
        if value and timezone.is_naive(value):
            value = timezone.make_aware(value, UTC)
        # If already aware, return as-is (middleware ensures it's UTC)
        return value
    
    def validate(self, data):
        check_in = data.get("check_in_time")
        check_out = data.get("check_out_time")

        if check_in and check_out and check_out < check_in:
            raise serializers.ValidationError("Check-out cannot be before check-in.")

        return data
    
    def update(self, instance, validated_data):
        # Extract base64_images if present and normalize to list
        base64_images = validated_data.pop('base64_images', None)
        if base64_images and isinstance(base64_images, str):
            base64_images = [base64_images]
        
        # Determine image type based on what's being updated
        image_type = 'check_out'
        captured_at = None
        
        if 'check_in_time' in validated_data:
            image_type = 'check_in'
            captured_at = validated_data.get('check_in_time')
        elif 'check_out_time' in validated_data:
            image_type = 'check_out'
            captured_at = validated_data.get('check_out_time')
        else:
            # Default to check_out if neither is being updated
            image_type = 'check_out'
            captured_at = instance.check_out_time or timezone.now()
        
        # Update attendance instance
        attendance = super().update(instance, validated_data)
        
        # Image processing removed - images are no longer stored
        return attendance
