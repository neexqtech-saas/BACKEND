"""
Simple Leave Management Serializers
"""

from rest_framework import serializers
from .models import LeaveType, EmployeeLeaveBalance, LeaveApplication
from AuthN.models import BaseUserModel


class LeaveTypeSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source='admin.email', read_only=True)
    
    class Meta:
        model = LeaveType
        fields = [
            'id', 'admin', 'site', 'name', 'code', 'default_count', 
            'is_paid', 'is_active', 'description', 'created_at', 'updated_at',
            'admin_email'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeaveTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'
        read_only_fields = ['id', 'admin', 'created_at', 'updated_at']


class EmployeeLeaveBalanceSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.own_user_profile.user_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_type_code = serializers.CharField(source='leave_type.code', read_only=True)
    
    def get_balance(self, obj):
        """Calculate balance safely"""
        try:
            return float(obj.assigned) - float(obj.used)
        except:
            return 0.0
    
    class Meta:
        model = EmployeeLeaveBalance
        fields = '__all__'
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']


class EmployeeLeaveBalanceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeLeaveBalance
        fields = ['id', 'user', 'leave_type', 'year', 'assigned', 'used', 'balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'leave_type', 'year', 'used', 'balance', 'created_at', 'updated_at']


class LeaveApplicationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.own_user_profile.user_name', read_only=True)
    custom_employee_id = serializers.CharField(source='user.own_user_profile.custom_employee_id', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_type_code = serializers.CharField(source='leave_type.code', read_only=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = LeaveApplication
        fields = '__all__'
        read_only_fields = ['id', 'applied_at']


class LeaveApplicationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveApplication
        fields = '__all__'
        read_only_fields = ['id', 'user', 'admin', 'organization', 'applied_at']
