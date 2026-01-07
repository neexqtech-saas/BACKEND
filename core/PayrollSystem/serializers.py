"""
Payroll System Serializers
"""
from rest_framework import serializers
from decimal import Decimal
from .models import (
    PayslipGenerator, ProfessionalTaxRule, OrganizationPayrollSettings,
    SalaryComponent, SalaryStructure, SalaryStructureItem, EmployeeBankInfo, EmployeeAdvance
)
from AuthN.models import BaseUserModel


# ==================== PAYSLIP GENERATOR SERIALIZERS ====================

class PayslipGeneratorSerializer(serializers.ModelSerializer):
    """Payslip Generator Serializer"""
    
    admin_id = serializers.IntegerField(source='admin.id', read_only=True)
    admin_name = serializers.CharField(source='admin.name', read_only=True)
    company_logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PayslipGenerator
        fields = [
            'id', 'payslip_number', 'admin_id', 'admin_name', 'employee',
            'month', 'year', 'pay_date', 'paid_days', 'loss_of_pay_days',
            'template', 'currency',
            'company_name', 'company_address', 'company_logo', 'company_logo_url',
            'employee_name', 'employee_code', 'designation', 'department', 'pan_number',
            'custom_employee_fields',
            'earnings', 'deductions', 'custom_pay_summary_fields',
            'total_earnings', 'total_deductions', 'net_pay',
            'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'payslip_number', 'created_at', 'updated_at']
    
    def get_company_logo_url(self, obj):
        if obj.company_logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.company_logo.url)
            return obj.company_logo.url
        return None


class PayslipGeneratorCreateSerializer(serializers.ModelSerializer):
    """Payslip Generator Create Serializer"""
    
    admin_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = PayslipGenerator
        fields = [
            'admin_id', 'employee',
            'month', 'year', 'pay_date', 'paid_days', 'loss_of_pay_days',
            'template', 'currency',
            'company_name', 'company_address', 'company_logo',
            'employee_name', 'employee_code', 'designation', 'department', 'pan_number',
            'custom_employee_fields',
            'earnings', 'deductions', 'custom_pay_summary_fields',
            'total_earnings', 'total_deductions', 'net_pay',
            'notes'
        ]
        read_only_fields = ['id', 'payslip_number']
    
    def validate_admin_id(self, value):
        try:
            admin = BaseUserModel.objects.get(id=value, role='admin')
            return value
        except BaseUserModel.DoesNotExist:
            raise serializers.ValidationError("Admin user not found")
    
    def create(self, validated_data):
        admin_id = validated_data.pop('admin_id')
        admin = BaseUserModel.objects.get(id=admin_id, role='admin')
        validated_data['admin'] = admin
        return super().create(validated_data)


class PayslipGeneratorUpdateSerializer(serializers.ModelSerializer):
    """Payslip Generator Update Serializer"""
    
    class Meta:
        model = PayslipGenerator
        fields = [
            'employee',
            'month', 'year', 'pay_date', 'paid_days', 'loss_of_pay_days',
            'template', 'currency',
            'company_name', 'company_address', 'company_logo',
            'employee_name', 'employee_code', 'designation', 'department', 'pan_number',
            'custom_employee_fields',
            'earnings', 'deductions', 'custom_pay_summary_fields',
            'total_earnings', 'total_deductions', 'net_pay',
            'notes'
        ]


class PayslipGeneratorListSerializer(serializers.ModelSerializer):
    """Payslip Generator List Serializer (minimal fields)"""
    
    class Meta:
        model = PayslipGenerator
        fields = ['id', 'payslip_number', 'month', 'year', 'employee_name', 'employee_code', 'net_pay', 'created_at']


# ==================== PROFESSIONAL TAX RULE SERIALIZERS ====================

class ProfessionalTaxRuleSerializer(serializers.ModelSerializer):
    """Professional Tax Rule Serializer"""
    
    class Meta:
        model = ProfessionalTaxRule
        fields = [
            'id', 'state_id', 'state_name', 'salary_from', 'salary_to',
            'tax_amount', 'applicable_month', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ==================== ORGANIZATION PAYROLL SETTINGS SERIALIZERS ====================

class OrganizationPayrollSettingsSerializer(serializers.ModelSerializer):
    """Organization Payroll Settings Serializer"""
    
    organization_id = serializers.UUIDField(source='organization.id', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = OrganizationPayrollSettings
        fields = [
            'id', 'organization_id', 'organization_name',
            # PF Fields
            'pf_employee_percentage', 'pf_employer_percentage', 'pf_wage_limit', 'pf_enabled',
            # ESI Fields
            'esi_employee_percentage', 'esi_employer_percentage', 'esi_wage_limit', 'esi_enabled',
            # Gratuity Fields
            'gratuity_percentage', 'gratuity_enabled',
            # PT Fields (TEMPORARY)
            'pt_fixed', 'pt_enabled',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'organization_id', 'organization_name']


class OrganizationPayrollSettingsCreateSerializer(serializers.ModelSerializer):
    """Organization Payroll Settings Create Serializer"""
    
    organization_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = OrganizationPayrollSettings
        fields = [
            'organization_id',
            # PF Fields (make percentages optional - will default to 12.0)
            'pf_employee_percentage', 'pf_employer_percentage', 'pf_wage_limit', 'pf_enabled',
            # ESI Fields
            'esi_employee_percentage', 'esi_employer_percentage', 'esi_wage_limit', 'esi_enabled',
            # Gratuity Fields
            'gratuity_percentage', 'gratuity_enabled',
            # PT Fields (TEMPORARY)
            'pt_fixed', 'pt_enabled',
        ]
        extra_kwargs = {
            'pf_employee_percentage': {'required': False},
            'pf_employer_percentage': {'required': False},
            'pf_wage_limit': {'required': False},
        }
    
    def validate_organization_id(self, value):
        try:
            organization = BaseUserModel.objects.get(id=value, role='organization')
            # Note: Settings existence check is now handled in the view
            return value
        except BaseUserModel.DoesNotExist:
            raise serializers.ValidationError("Organization not found")
    
    def validate_pf_employee_percentage(self, value):
        # Enforce statutory value - always 12%
        # Allow None/not provided - will be set to 12.0 in create method
        if value is not None and value != 12.0:
            raise serializers.ValidationError("PF employee percentage must be 12% (statutory rate). Cannot be modified.")
        return 12.0 if value is None else value
    
    def validate_pf_employer_percentage(self, value):
        # Enforce statutory value - always 12%
        # Allow None/not provided - will be set to 12.0 in create method
        if value is not None and value != 12.0:
            raise serializers.ValidationError("PF employer percentage must be 12% (statutory rate). Cannot be modified.")
        return 12.0 if value is None else value
    
    def validate_pf_wage_limit(self, value):
        # PF wage limit is editable (default is ₹15,000 statutory limit)
        if value < 0:
            raise serializers.ValidationError("PF wage limit cannot be negative.")
        return value  # Allow user to set custom wage limit
    
    def create(self, validated_data):
        organization_id = validated_data.pop('organization_id')
        organization = BaseUserModel.objects.get(id=organization_id, role='organization')
        validated_data['organization'] = organization
        # Ensure PF values are set to statutory defaults (enforced by validation)
        validated_data['pf_employee_percentage'] = 12.0
        validated_data['pf_employer_percentage'] = 12.0
        validated_data['pf_wage_limit'] = 15000.00
        return super().create(validated_data)


class OrganizationPayrollSettingsUpdateSerializer(serializers.ModelSerializer):
    """Organization Payroll Settings Update Serializer"""
    
    # Make pt_fixed optional (not required from frontend - will use state-wise rules)
    pt_fixed = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    
    # PF fields are kept for backward compatibility but will be enforced to statutory values
    pf_employee_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    pf_employer_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    pf_wage_limit = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    class Meta:
        model = OrganizationPayrollSettings
        fields = [
            # PF Fields
            'pf_employee_percentage', 'pf_employer_percentage', 'pf_wage_limit', 'pf_enabled',
            # ESI Fields
            'esi_employee_percentage', 'esi_employer_percentage', 'esi_wage_limit', 'esi_enabled',
            # Gratuity Fields
            'gratuity_percentage', 'gratuity_enabled',
            # PT Fields - pt_fixed is optional (state-wise auto calculation)
            'pt_fixed', 'pt_enabled',
        ]
    
    def validate_pf_employee_percentage(self, value):
        # Enforce statutory value - always 12%
        if value is not None and value != 12.0:
            raise serializers.ValidationError("PF employee percentage must be 12% (statutory rate). Cannot be modified.")
        return 12.0  # Always return statutory value
    
    def validate_pf_employer_percentage(self, value):
        # Enforce statutory value - always 12%
        if value is not None and value != 12.0:
            raise serializers.ValidationError("PF employer percentage must be 12% (statutory rate). Cannot be modified.")
        return 12.0  # Always return statutory value
    
    def validate_pf_wage_limit(self, value):
        # PF wage limit is editable (default is ₹15,000 statutory limit)
        if value is not None and value < 0:
            raise serializers.ValidationError("PF wage limit cannot be negative.")
        return value  # Allow user to set custom wage limit


# ==================== SALARY STRUCTURE SERIALIZERS (UNIFIED API) ====================

class SalaryStructureItemResponseSerializer(serializers.Serializer):
    """Serializer for structure item in GET response"""
    component = serializers.CharField()  # Component code (BASIC, SPECIAL_ALLOWANCE, PF, etc.)
    label = serializers.CharField()  # Display name
    calculation_type = serializers.CharField()
    value = serializers.CharField()  # Can be number, percentage string, or "Auto"
    editable = serializers.BooleanField()


class SalaryStructureResponseSerializer(serializers.Serializer):
    """Unified GET response serializer"""
    structure_id = serializers.IntegerField()
    name = serializers.CharField()
    earnings = SalaryStructureItemResponseSerializer(many=True)
    deductions = SalaryStructureItemResponseSerializer(many=True)


class EarningsUpdateItemSerializer(serializers.Serializer):
    """Serializer for earnings update in PUT"""
    component = serializers.CharField(required=True)  # Component code
    label = serializers.CharField(required=False, allow_blank=True)  # Display name (optional)
    calculation_type = serializers.ChoiceField(choices=['fixed', 'percentage'], required=True)
    value = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    calculation_base = serializers.CharField(required=False, allow_null=True)  # Component code for percentage base


class DeductionsUpdateItemSerializer(serializers.Serializer):
    """Serializer for deductions update in PUT (non-statutory only)"""
    component = serializers.CharField(required=True)  # Component code
    label = serializers.CharField(required=False, allow_blank=True)  # Display name (optional)
    calculation_type = serializers.ChoiceField(choices=['fixed', 'percentage'], required=True)
    value = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    calculation_base = serializers.CharField(required=False, allow_null=True)  # Component code for percentage base


class SalaryStructureCreateSerializer(serializers.Serializer):
    """Serializer for POST (create) - accepts earnings and deductions"""
    name = serializers.CharField(required=True)
    is_default = serializers.BooleanField(default=False)
    description = serializers.CharField(required=False, allow_blank=True)
    earnings = EarningsUpdateItemSerializer(many=True, required=False)  # Optional custom earnings
    deductions = DeductionsUpdateItemSerializer(many=True, required=False)  # Optional non-statutory deductions


class SalaryStructureUpdateSerializer(serializers.Serializer):
    """Serializer for PUT (update) - name, earnings and non-statutory deductions"""
    name = serializers.CharField(required=False)  # Optional - can update name
    earnings = EarningsUpdateItemSerializer(many=True, required=True)
    deductions = DeductionsUpdateItemSerializer(many=True, required=False)  # Optional, only non-statutory


# ==================== EMPLOYEE PAYROLL CONFIG SERIALIZERS ====================

class EmployeePayrollConfigCreateUpdateSerializer(serializers.Serializer):
    """Serializer for POST/PUT - Input data for EmployeePayrollConfig"""
    employee_id = serializers.UUIDField(required=True)
    salary_structure_id = serializers.IntegerField(required=True)
    gross_salary = serializers.DecimalField(max_digits=12, decimal_places=2, required=True, min_value=Decimal('0.01'))
    effective_month = serializers.IntegerField(required=True, min_value=1, max_value=12)
    effective_year = serializers.IntegerField(required=True)
    pf_applicable = serializers.BooleanField(required=False, allow_null=True)
    esi_applicable = serializers.BooleanField(required=False, allow_null=True)
    pt_applicable = serializers.BooleanField(required=False, allow_null=True)
    gratuity_applicable = serializers.BooleanField(required=False, allow_null=True)


class EmployeePayrollConfigResponseSerializer(serializers.Serializer):
    """Serializer for GET response - includes calculated earnings and deductions"""
    id = serializers.IntegerField()
    employee_id = serializers.UUIDField()
    salary_structure = serializers.IntegerField()
    effective_month = serializers.IntegerField()
    effective_year = serializers.IntegerField()
    gross_salary = serializers.DecimalField(max_digits=12, decimal_places=2)
    earnings = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        )
    )
    deductions = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        )
    )
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_deductions = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_pay = serializers.DecimalField(max_digits=12, decimal_places=2)


# ==================== EMPLOYEE BANK INFO SERIALIZERS ====================

class EmployeeBankInfoSerializer(serializers.ModelSerializer):
    """Employee Bank Info Serializer - Full details"""
    
    employee_id = serializers.UUIDField(source='employee.id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    custom_employee_id = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeBankInfo
        fields = [
            'id', 'employee_id', 'employee_name', 'custom_employee_id',
            'pan_card_number', 'pan_card_name',
            'aadhar_card_number', 'aadhar_card_name',
            'bank_name', 'account_number', 'account_holder_name', 'account_type',
            'ifsc_code', 'bank_address', 'branch_name',
            'city', 'state', 'pincode',
            'is_primary', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_employee_name(self, obj):
        """Get employee name from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.user_name
        return obj.employee.name if hasattr(obj.employee, 'name') else None
    
    def get_custom_employee_id(self, obj):
        """Get custom employee ID from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.custom_employee_id
        return None


class EmployeeBankInfoCreateSerializer(serializers.ModelSerializer):
    """Employee Bank Info Create Serializer"""
    
    employee_id = serializers.UUIDField(write_only=True, required=True)
    
    class Meta:
        model = EmployeeBankInfo
        fields = [
            'employee_id',
            'pan_card_number', 'pan_card_name',
            'aadhar_card_number', 'aadhar_card_name',
            'bank_name', 'account_number', 'account_holder_name', 'account_type',
            'ifsc_code', 'bank_address', 'branch_name',
            'city', 'state', 'pincode',
            'is_primary', 'is_active'
        ]
    
    def validate_employee_id(self, value):
        """Validate that employee exists and has role 'user'"""
        try:
            employee = BaseUserModel.objects.get(id=value, role='user')
            return value
        except BaseUserModel.DoesNotExist:
            raise serializers.ValidationError("Employee not found")
    
    def create(self, validated_data):
        """Create bank info with employee"""
        employee_id = validated_data.pop('employee_id')
        employee = BaseUserModel.objects.get(id=employee_id, role='user')
        
        # If setting as primary, unset other primary accounts for this employee
        if validated_data.get('is_primary', True):
            EmployeeBankInfo.objects.filter(employee=employee, is_primary=True).update(is_primary=False)
        
        validated_data['employee'] = employee
        return super().create(validated_data)


class EmployeeBankInfoUpdateSerializer(serializers.ModelSerializer):
    """Employee Bank Info Update Serializer"""
    
    class Meta:
        model = EmployeeBankInfo
        fields = [
            'pan_card_number', 'pan_card_name',
            'aadhar_card_number', 'aadhar_card_name',
            'bank_name', 'account_number', 'account_holder_name', 'account_type',
            'ifsc_code', 'bank_address', 'branch_name',
            'city', 'state', 'pincode',
            'is_primary', 'is_active'
        ]
    
    def update(self, instance, validated_data):
        """Update bank info"""
        # If setting as primary, unset other primary accounts for this employee
        if validated_data.get('is_primary', False):
            EmployeeBankInfo.objects.filter(
                employee=instance.employee,
                is_primary=True
            ).exclude(id=instance.id).update(is_primary=False)
        
        return super().update(instance, validated_data)


class EmployeeBankInfoListSerializer(serializers.ModelSerializer):
    """Employee Bank Info List Serializer - Minimal fields for list view"""
    
    employee_id = serializers.UUIDField(source='employee.id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    custom_employee_id = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeBankInfo
        fields = [
            'id', 'employee_id', 'employee_name', 'custom_employee_id',
            'bank_name', 'account_number', 'account_type', 'ifsc_code',
            'is_primary', 'is_active', 'created_at'
        ]
    
    def get_employee_name(self, obj):
        """Get employee name from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.user_name
        return obj.employee.name if hasattr(obj.employee, 'name') else None
    
    def get_custom_employee_id(self, obj):
        """Get custom employee ID from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.custom_employee_id
        return None


# ==================== EMPLOYEE ADVANCE SERIALIZERS ====================

class EmployeeAdvanceSerializer(serializers.ModelSerializer):
    """Employee Advance Serializer - Full details"""
    
    employee_id = serializers.UUIDField(source='employee.id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    custom_employee_id = serializers.SerializerMethodField()
    admin_id = serializers.UUIDField(source='admin.id', read_only=True)
    created_by_id = serializers.UUIDField(source='created_by.id', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeAdvance
        fields = [
            'id', 'employee_id', 'employee_name', 'custom_employee_id',
            'admin_id', 'created_by_id', 'created_by_name',
            'advance_amount', 'request_date', 'purpose', 'status',
            'paid_amount', 'remaining_amount', 'is_settled', 'settlement_date',
            'notes', 'attachment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'remaining_amount', 'is_settled', 'settlement_date', 'created_at', 'updated_at']
    
    def get_employee_name(self, obj):
        """Get employee name from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.user_name
        return obj.employee.name if hasattr(obj.employee, 'name') else None
    
    def get_custom_employee_id(self, obj):
        """Get custom employee ID from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.custom_employee_id
        return None
    
    def get_created_by_name(self, obj):
        """Get created by name"""
        if obj.created_by:
            if obj.created_by.role == 'admin' and hasattr(obj.created_by, 'own_admin_profile'):
                return obj.created_by.own_admin_profile.admin_name
            return obj.created_by.name if hasattr(obj.created_by, 'name') else None
        return None


class EmployeeAdvanceCreateSerializer(serializers.ModelSerializer):
    """Employee Advance Create Serializer"""
    
    employee_id = serializers.UUIDField(write_only=True, required=True)
    
    class Meta:
        model = EmployeeAdvance
        fields = [
            'employee_id',
            'advance_amount', 'request_date', 'purpose', 'status',
            'notes', 'attachment'
        ]
    
    def validate_employee_id(self, value):
        """Validate that employee exists and has role 'user'"""
        try:
            employee = BaseUserModel.objects.get(id=value, role='user')
            return value
        except BaseUserModel.DoesNotExist:
            raise serializers.ValidationError("Employee not found")
    
    def validate_advance_amount(self, value):
        """Validate advance amount"""
        if value <= 0:
            raise serializers.ValidationError("Advance amount must be greater than 0")
        return value
    
    def create(self, validated_data):
        """Create advance with employee and admin"""
        employee_id = validated_data.pop('employee_id')
        employee = BaseUserModel.objects.get(id=employee_id, role='user')
        
        # Get admin from context (set in view)
        admin = self.context.get('admin')
        created_by = self.context.get('created_by')
        
        # Set remaining_amount to advance_amount initially
        advance_amount = validated_data.get('advance_amount')
        validated_data['employee'] = employee
        validated_data['admin'] = admin
        validated_data['created_by'] = created_by
        validated_data['remaining_amount'] = advance_amount
        
        return super().create(validated_data)


class EmployeeAdvanceUpdateSerializer(serializers.ModelSerializer):
    """Employee Advance Update Serializer"""
    
    class Meta:
        model = EmployeeAdvance
        fields = [
            'advance_amount', 'request_date', 'purpose', 'status',
            'paid_amount', 'notes', 'attachment'
        ]
    
    def validate_advance_amount(self, value):
        """Validate advance amount"""
        if value <= 0:
            raise serializers.ValidationError("Advance amount must be greater than 0")
        return value
    
    def validate_paid_amount(self, value):
        """Validate paid amount"""
        if value < 0:
            raise serializers.ValidationError("Paid amount cannot be negative")
        return value
    
    def update(self, instance, validated_data):
        """Update advance - remaining_amount will be auto-calculated in save()"""
        # If advance_amount is updated, recalculate remaining_amount
        if 'advance_amount' in validated_data:
            new_advance_amount = validated_data['advance_amount']
            paid_amount = validated_data.get('paid_amount', instance.paid_amount)
            validated_data['remaining_amount'] = new_advance_amount - paid_amount
        
        # If paid_amount is updated, recalculate remaining_amount
        if 'paid_amount' in validated_data:
            paid_amount = validated_data['paid_amount']
            advance_amount = validated_data.get('advance_amount', instance.advance_amount)
            validated_data['remaining_amount'] = advance_amount - paid_amount
        
        return super().update(instance, validated_data)


class EmployeeAdvanceListSerializer(serializers.ModelSerializer):
    """Employee Advance List Serializer - Minimal fields for list view"""
    
    employee_id = serializers.UUIDField(source='employee.id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    custom_employee_id = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeAdvance
        fields = [
            'id', 'employee_id', 'employee_name', 'custom_employee_id',
            'advance_amount', 'paid_amount', 'remaining_amount',
            'request_date', 'status', 'is_settled',
            'created_at'
        ]
    
    def get_employee_name(self, obj):
        """Get employee name from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.user_name
        return obj.employee.name if hasattr(obj.employee, 'name') else None
    
    def get_custom_employee_id(self, obj):
        """Get custom employee ID from UserProfile"""
        if hasattr(obj.employee, 'own_user_profile'):
            return obj.employee.own_user_profile.custom_employee_id
        return None