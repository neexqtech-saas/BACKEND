"""
Task Management Serializers
"""

from rest_framework import serializers
from .models import TaskType, Task, TaskComment
from AuthN.models import BaseUserModel


class TaskTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskType
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaskTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskType
        fields = '__all__'
        read_only_fields = ['id', 'admin', 'created_at', 'updated_at']


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_custom_employee_id = serializers.SerializerMethodField()
    assigned_by_email = serializers.EmailField(source='assigned_by.email', read_only=True, allow_null=True)
    assigned_by_name = serializers.SerializerMethodField()
    assigned_by_custom_employee_id = serializers.SerializerMethodField()
    task_type_name = serializers.CharField(source='task_type.name', read_only=True)
    
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_scheduled_instance']
    
    def get_assigned_to_name(self, obj):
        """Get the name of the assigned employee"""
        if obj.assigned_to and hasattr(obj.assigned_to, 'own_user_profile'):
            return obj.assigned_to.own_user_profile.user_name
        return obj.assigned_to.email if obj.assigned_to else None
    
    def get_assigned_to_custom_employee_id(self, obj):
        """Get the custom employee ID of the assigned employee"""
        if obj.assigned_to and hasattr(obj.assigned_to, 'own_user_profile'):
            return obj.assigned_to.own_user_profile.custom_employee_id
        return None
    
    def get_assigned_by_name(self, obj):
        """Get the name of the person who assigned the task"""
        if obj.assigned_by and hasattr(obj.assigned_by, 'own_user_profile'):
            return obj.assigned_by.own_user_profile.user_name
        return obj.assigned_by.email if obj.assigned_by else None
    
    def get_assigned_by_custom_employee_id(self, obj):
        """Get the custom employee ID of the person who assigned the task"""
        if obj.assigned_by and hasattr(obj.assigned_by, 'own_user_profile'):
            return obj.assigned_by.own_user_profile.custom_employee_id
        return None
    
    def validate(self, data):
        """Validate schedule frequency and related fields"""
        schedule_frequency = data.get('schedule_frequency', 'onetime')
        
        # Weekly requires week_day
        if schedule_frequency == 'weekly' and not data.get('week_day'):
            raise serializers.ValidationError({
                'week_day': 'Week day is required for weekly schedule'
            })
        
        # Monthly requires month_date
        if schedule_frequency == 'monthly' and not data.get('month_date'):
            raise serializers.ValidationError({
                'month_date': 'Month date is required for monthly schedule'
            })
        
        # Validate week_day range (0-6)
        if data.get('week_day'):
            try:
                week_day = int(data['week_day'])
                if week_day < 0 or week_day > 6:
                    raise serializers.ValidationError({
                        'week_day': 'Week day must be between 0 (Monday) and 6 (Sunday)'
                    })
            except (ValueError, TypeError):
                raise serializers.ValidationError({
                    'week_day': 'Week day must be a number between 0 and 6'
                })
        
        # Validate month_date range (1-31)
        if data.get('month_date'):
            month_date = data['month_date']
            if month_date < 1 or month_date > 31:
                raise serializers.ValidationError({
                    'month_date': 'Month date must be between 1 and 31'
                })
        
        return data


class TaskCommentSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source='admin.email', read_only=True)
    admin_name = serializers.CharField(source='admin.own_user_profile.user_name', read_only=True)
    
    class Meta:
        model = TaskComment
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
