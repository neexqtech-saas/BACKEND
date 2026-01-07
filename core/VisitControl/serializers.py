"""
Visit Management Serializers
"""

from rest_framework import serializers
from .models import Visit
from AuthN.models import BaseUserModel


class VisitSerializer(serializers.ModelSerializer):
    """Serializer for Visit"""
    assigned_employee_email = serializers.EmailField(source='assigned_employee.email', read_only=True)
    assigned_employee_name = serializers.SerializerMethodField()
    custom_employee_id = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Visit
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'check_in_timestamp', 'check_in_latitude', 'check_in_longitude',
            'check_out_timestamp', 'check_out_latitude', 'check_out_longitude',
            'status'
        ]
    
    def get_assigned_employee_name(self, obj):
        """Get the name of the assigned employee"""
        if obj.assigned_employee and hasattr(obj.assigned_employee, 'own_user_profile'):
            return obj.assigned_employee.own_user_profile.user_name
        return obj.assigned_employee.email if obj.assigned_employee else None
    
    def get_custom_employee_id(self, obj):
        """Get the custom employee ID of the assigned employee"""
        if obj.assigned_employee and hasattr(obj.assigned_employee, 'own_user_profile'):
            return obj.assigned_employee.own_user_profile.custom_employee_id
        return None
    
    def get_created_by_name(self, obj):
        """Get the name of the user who created the visit"""
        if obj.created_by:
            if obj.created_by.role == 'user' and hasattr(obj.created_by, 'own_user_profile'):
                return obj.created_by.own_user_profile.user_name
            elif obj.created_by.role == 'admin' and hasattr(obj.created_by, 'own_admin_profile'):
                return obj.created_by.own_admin_profile.admin_name
            return obj.created_by.email
        return None


class VisitCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Visit"""
    
    class Meta:
        model = Visit
        fields = [
            'title', 'description', 'schedule_date', 'schedule_time',
            'client_name', 'location_name', 'address', 'city', 'state', 'pincode', 'country',
            'contact_person', 'contact_phone', 'contact_email',
            'assigned_employee'
        ]
    
    def validate(self, data):
        """Validate visit data"""
        from django.utils import timezone
        if data.get('schedule_date') and data['schedule_date'] < timezone.now().date():
            pass
        return data


class VisitCheckInSerializer(serializers.Serializer):
    """Serializer for Check-In action"""
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        required=True,
        help_text="GPS latitude coordinate"
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        required=True,
        help_text="GPS longitude coordinate"
    )
    note = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Optional note for check-in"
    )
    
    def validate(self, data):
        """Validate check-in data"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if latitude is not None:
            if not (-90 <= float(latitude) <= 90):
                raise serializers.ValidationError({
                    'latitude': 'Latitude must be between -90 and 90 degrees.'
                })
        
        if longitude is not None:
            if not (-180 <= float(longitude) <= 180):
                raise serializers.ValidationError({
                    'longitude': 'Longitude must be between -180 and 180 degrees.'
                })
        
        return data


class VisitCheckOutSerializer(serializers.Serializer):
    """Serializer for Check-Out action"""
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        required=True,
        help_text="GPS latitude coordinate"
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        required=True,
        help_text="GPS longitude coordinate"
    )
    note = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Optional note for check-out"
    )
    
    def validate(self, data):
        """Validate check-out data"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if latitude is not None:
            if not (-90 <= float(latitude) <= 90):
                raise serializers.ValidationError({
                    'latitude': 'Latitude must be between -90 and 90 degrees.'
                })
        
        if longitude is not None:
            if not (-180 <= float(longitude) <= 180):
                raise serializers.ValidationError({
                    'longitude': 'Longitude must be between -180 and 180 degrees.'
                })
        
        return data
