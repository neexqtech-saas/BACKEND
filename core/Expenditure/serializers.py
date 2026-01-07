"""
Expenditure Serializers
"""

from rest_framework import serializers
from .models import ExpenseCategory, ExpenseProject, Expense
from AuthN.models import BaseUserModel


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Validate unique code per admin"""
        if value:
            admin = self.initial_data.get('admin')
            if admin:
                existing = ExpenseCategory.objects.filter(
                    admin_id=admin,
                    code=value,
                    is_active=True
                ).exclude(id=self.instance.id if self.instance else None)
                if existing.exists():
                    raise serializers.ValidationError("Code already exists for this admin")
        return value


class ExpenseProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseProject
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Validate unique code per admin"""
        if value:
            admin = self.initial_data.get('admin')
            if admin:
                existing = ExpenseProject.objects.filter(
                    admin_id=admin,
                    code=value,
                    is_active=True
                ).exclude(id=self.instance.id if self.instance else None)
                if existing.exists():
                    raise serializers.ValidationError("Code already exists for this admin")
        return value


class ExpenseSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.own_user_profile.user_name', read_only=True, allow_null=True)
    employee_email = serializers.EmailField(source='employee.email', read_only=True)
    employee_custom_employee_id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.own_user_profile.user_name', read_only=True, allow_null=True)
    approved_by_email = serializers.EmailField(source='approved_by.email', read_only=True, allow_null=True)
    rejected_by_name = serializers.CharField(source='rejected_by.own_user_profile.user_name', read_only=True, allow_null=True)
    rejected_by_email = serializers.EmailField(source='rejected_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'approved_at', 'rejected_at', 'submitted_at']
    
    def get_employee_custom_employee_id(self, obj):
        """Get the custom employee ID of the employee"""
        if obj.employee and hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.custom_employee_id
        return None


class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'admin', 'employee', 'category', 'project', 'title', 'description', 'expense_date', 'amount',
            'currency', 'receipts', 'supporting_documents', 'remarks', 'status', 'submitted_at', 'created_by'
        ]
        read_only_fields = ['status', 'submitted_at', 'created_by']
    
    def validate(self, data):
        """Validate required fields"""
        required_fields = ['category', 'project', 'title', 'description', 'expense_date', 'amount']
        for field in required_fields:
            if field not in data or (isinstance(data[field], str) and not data[field].strip()):
                raise serializers.ValidationError({field: f"{field.replace('_', ' ').title()} is required"})
        return data
    
    def create(self, validated_data):
        # Set status to 'pending' when employee creates expense
        validated_data['status'] = 'pending'
        return super().create(validated_data)
