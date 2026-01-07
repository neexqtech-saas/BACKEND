"""
Payroll System Models
"""
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from AuthN.models import BaseUserModel
from SiteManagement.models import Site


class PayslipGenerator(models.Model):
    """Payslip Generator Model"""
    
    TEMPLATE_CHOICES = [
        ('classic', 'Classic'),
        ('modern', 'Modern'),
        ('minimal', 'Minimal'),
        ('elegant', 'Elegant'),
        ('corporate', 'Corporate'),
        ('colorful', 'Colorful'),
        ('professional', 'Professional'),
        ('vibrant', 'Vibrant'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        related_name='admin_payslips'
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payslips',
        help_text="Site associated with this payslip"
    )
    
    # Employee Reference (optional - can be null)
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'user'},
        related_name='employee_payslips',
        help_text="Employee for whom this payslip is generated (optional)"
    )
    
    # Payslip Details
    payslip_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    pay_date = models.DateField()
    paid_days = models.IntegerField(default=0)
    loss_of_pay_days = models.IntegerField(default=0)
    template = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='classic')
    currency = models.CharField(max_length=10, default='INR')
    
    # Company Details
    company_name = models.CharField(max_length=255, blank=True, null=True)
    company_address = models.TextField(blank=True, null=True)
    company_logo = models.ImageField(upload_to='payslip_logos/', blank=True, null=True)
    
    # Employee Details
    employee_name = models.CharField(max_length=255)
    employee_code = models.CharField(max_length=100, blank=True, null=True, help_text="Custom employee ID code (legacy field)")
    designation = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    pan_number = models.CharField(max_length=10, blank=True, null=True)
    custom_employee_fields = models.JSONField(default=dict, blank=True)
    
    # Earnings and Deductions
    earnings = models.JSONField(default=list, blank=True)
    deductions = models.JSONField(default=list, blank=True)
    custom_pay_summary_fields = models.JSONField(default=dict, blank=True)
    
    # Totals
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Notes
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payslip_generator'
        ordering = ['-created_at']
        verbose_name = 'Custom Payslip Generator'
        verbose_name_plural = 'Custom Payslip Generators'
        indexes = [
            models.Index(fields=['admin', 'created_at'], name='payslip_adm_created_idx'),
            models.Index(fields=['employee', 'year', 'month'], name='payslip_emp_year_month_idx'),
            models.Index(fields=['id', 'admin'], name='payslip_id_adm_idx'),
        ]
    
    def save(self, *args, **kwargs):
        if not self.payslip_number:
            # Generate payslip number if not provided
            from datetime import datetime
            prefix = f"PSL-{self.year}-{self.month[:3].upper()}-"
            last_payslip = PayslipGenerator.objects.filter(
                payslip_number__startswith=prefix
            ).order_by('-id').first()
            
            if last_payslip and last_payslip.payslip_number:
                try:
                    last_num = int(last_payslip.payslip_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.payslip_number = f"{prefix}{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.payslip_number} - {self.employee_name} ({self.month} {self.year})"


class ProfessionalTaxRule(models.Model):
    """Professional Tax Rule Model"""
    
    id = models.BigAutoField(primary_key=True)
    state_id = models.BigIntegerField()
    state_name = models.CharField(max_length=100)
    salary_from = models.DecimalField(max_digits=12, decimal_places=2)
    salary_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    applicable_month = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'professional_tax_rule'
        ordering = ['state_name', 'salary_from']
        verbose_name = 'Professional Tax Rule'
        verbose_name_plural = 'Professional Tax Rules'
        indexes = [
            models.Index(fields=['state_id', 'is_active', 'salary_from'], name='ptrule_state_active_sal_idx'),
            models.Index(fields=['state_name', 'is_active'], name='ptrule_state_name_active_idx'),
        ]
    
    def __str__(self):
        month_str = f"Month {self.applicable_month}" if self.applicable_month else "All Months"
        to_str = f" to {self.salary_to}" if self.salary_to else " and above"
        return f"{self.state_name} - {self.salary_from}{to_str} - {self.tax_amount} ({month_str})"


class OrganizationPayrollSettings(models.Model):
    """Organization Payroll Settings Model"""
    
    organization = models.OneToOneField(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'organization'},
        related_name="payroll_settings"
    )

    # PF (Provident Fund)
    pf_employee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=12.0)
    pf_employer_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=12.0)
    pf_wage_limit = models.DecimalField(max_digits=10, decimal_places=2, default=15000.00)
    pf_enabled = models.BooleanField(default=False)

    # ESI (Employee State Insurance)
    esi_employee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.75)
    esi_employer_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=3.25)
    esi_wage_limit = models.DecimalField(max_digits=10, decimal_places=2, default=21000.00)
    esi_enabled = models.BooleanField(default=False)

    # Gratuity
    gratuity_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=4.81)
    gratuity_enabled = models.BooleanField(default=False)

    # Professional Tax - State-wise auto calculation (pt_fixed kept for backward compatibility)
    pt_fixed = models.DecimalField(max_digits=10, decimal_places=2, default=200.00, null=True, blank=True)
    pt_enabled = models.BooleanField(default=False, help_text="Enable Professional Tax - will be calculated state-wise automatically")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organization_payroll_settings'
        verbose_name = 'Organization Payroll Settings'
        verbose_name_plural = 'Organization Payroll Settings'
    
    def __str__(self):
        return f"Payroll Settings - {self.organization.name if hasattr(self.organization, 'name') else self.organization.id}"

# ==================== SALARY COMPONENT (MASTER) ====================
class SalaryComponent(models.Model):
    """
    Salary Component Master Model
    Reusable, org-wise, statutory protected
    """
    
    EARNING = "earning"
    DEDUCTION = "deduction"
    COMPONENT_TYPES = [
        (EARNING, "Earning"),
        (DEDUCTION, "Deduction"),
    ]
    
    STATUTORY_TYPES = [
        ("PF", "Provident Fund"),
        ("ESI", "ESIC"),
        ("PT", "Professional Tax"),
        ("GRATUITY", "Gratuity"),
    ]
    
    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'organization'},
        related_name='organization_salary_components'
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, help_text="Unique code per organization (auto-uppercase)")
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPES)
    statutory_type = models.CharField(
        max_length=20, 
        choices=STATUTORY_TYPES, 
        null=True, 
        blank=True,
        help_text="If set, this component is statutory and values are auto-calculated"
    )
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'salary_component'
        unique_together = ("organization", "code")
        ordering = ['name']
        verbose_name = 'Salary Component'
        verbose_name_plural = 'Salary Components'
        indexes = [
            models.Index(fields=['organization', 'is_active'], name='salcomp_org_active_idx'),
            models.Index(fields=['organization', 'component_type'], name='salcomp_org_type_idx'),
            models.Index(fields=['id', 'organization'], name='salcomp_id_org_idx'),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-uppercase code
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)
    
    def __str__(self):
        statutory = f" [{self.statutory_type}]" if self.statutory_type else ""
        return f"{self.name} ({self.code}){statutory}"


# ==================== SALARY STRUCTURE (TEMPLATE) ====================
class SalaryStructure(models.Model):
    """
    Salary Structure Template Model
    Monthly CTC / Custom templates
    """
    
    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'organization'},
        related_name='organization_salary_structures'
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'salary_structure'
        ordering = ['name']
        verbose_name = 'Salary Structure'
        verbose_name_plural = 'Salary Structures'
        indexes = [
            models.Index(fields=['organization', 'is_active'], name='salstruct_org_active_idx'),
            models.Index(fields=['id', 'organization'], name='salstruct_id_org_idx'),
        ]
    
    def __str__(self):
        return self.name


# ==================== SALARY STRUCTURE ITEM (BREAKUP) ====================
class SalaryStructureItem(models.Model):
    """
    Salary Structure Item Model
    Links components to structures with calculation rules
    Statutory value NOT stored here - fetched at runtime
    """
    
    CALCULATION_TYPES = [
        ("fixed", "Fixed"),
        ("percentage", "Percentage"),
        ("auto", "Auto"),
    ]
    
    id = models.BigAutoField(primary_key=True)
    structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.CASCADE,
        related_name="items"
    )
    component = models.ForeignKey(
        SalaryComponent,
        on_delete=models.PROTECT,
        related_name="structure_items"
    )
    
    calculation_type = models.CharField(
        max_length=20,
        choices=CALCULATION_TYPES,
        help_text="Auto for statutory components"
    )
    
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Null for statutory components - fetched at runtime"
    )
    
    calculation_base = models.ForeignKey(
        SalaryComponent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dependent_items",
        help_text="Component to base percentage calculation on"
    )
    
    order = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'salary_structure_item'
        unique_together = ("structure", "component")
        ordering = ['order', 'id']
        verbose_name = 'Salary Structure Item'
        verbose_name_plural = 'Salary Structure Items'
    
    
    def __str__(self):
        return f"{self.structure.name} - {self.component.name} ({self.calculation_type})"


# ==================== EMPLOYEE PAYROLL CONFIG ====================
class EmployeePayrollConfig(models.Model):
    """
    FINAL Employee Payroll Configuration
    Rules:
    - Only Gross Salary is editable
    - Salary breakup comes from SalaryStructure
    - PF & ESI eligibility can be overridden at employee level
    - PT & Gratuity applicability allowed for special / exempt cases
    - TDS is always system calculated
    """
    
    id = models.BigAutoField(primary_key=True)
    
    # --------------------
    # Ownership
    # --------------------
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "admin"},
        related_name="employee_payroll_configs"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_configs',
        help_text="Site associated with this payroll config"
    )
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "user"},
        related_name="payroll_config"
    )
    salary_structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.PROTECT,
        related_name="employee_payroll_configs"
    )
    
    # --------------------
    # Salary Input (ONLY editable amount)
    # --------------------
    gross_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monthly gross salary"
    )
    
    # --------------------
    # Effective Period
    # --------------------
    effective_month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month when this payroll config becomes effective (1-12)"
    )
    effective_year = models.IntegerField(
        help_text="Year when this payroll config becomes effective"
    )
    
    # --------------------
    # Statutory Applicability (Employee Level)
    # NULL = system decides
    # True = force applicable
    # False = force not applicable
    # --------------------
    pf_applicable = models.BooleanField(
        null=True,
        blank=True,
        help_text="PF applicability override for this employee"
    )
    esi_applicable = models.BooleanField(
        null=True,
        blank=True,
        help_text="ESI applicability override for this employee"
    )
    pt_applicable = models.BooleanField(
        null=True,
        blank=True,
        help_text="Professional Tax applicability override (exempt / special cases)"
    )
    gratuity_applicable = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether gratuity policy applies to this employee"
    )
    
    # --------------------
    # Status
    # --------------------
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "employee_payroll_config"
        unique_together = ("employee", "effective_month", "effective_year")
        verbose_name = "Employee Payroll Configuration"
        verbose_name_plural = "Employee Payroll Configurations"
        ordering = ['-effective_year', '-effective_month']
        indexes = [
            models.Index(fields=['admin', 'is_active', 'effective_year', 'effective_month'], name='payconfig_adm_active_ym_idx'),
            models.Index(fields=['employee', 'effective_year', 'effective_month'], name='payconfig_emp_ym_idx'),
            models.Index(fields=['id', 'admin'], name='payconfig_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'is_active', 'effective_year', 'effective_month'], name='payconfig_site_adm_act_ym'),
        ]
    
    def __str__(self):
        return f"{self.employee.id} | Gross ₹{self.gross_salary} | {self.effective_month}/{self.effective_year}"


# ==================== EMPLOYEE BANK INFORMATION ====================
class EmployeeBankInfo(models.Model):
    """
    Employee Bank Account Information
    Stores bank details for salary payments
    """
    
    ACCOUNT_TYPE_CHOICES = [
        ('savings', 'Savings Account'),
        ('current', 'Current Account'),
        ('salary', 'Salary Account'),
        ('fixed_deposit', 'Fixed Deposit Account'),
        ('recurring_deposit', 'Recurring Deposit Account'),
        ('nre', 'NRE Account'),
        ('nro', 'NRO Account'),
        ('fcnr', 'FCNR Account'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    
    # --------------------
    # Ownership
    # --------------------
    employee = models.OneToOneField(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "user"},
        related_name="bank_info",
        help_text="Employee for whom this bank information is stored"
    )
    
    # --------------------
    # PAN Card Information
    # --------------------
    pan_card_number = models.CharField(
        max_length=10,
        unique=True,
        null=False,
        blank=False,
        help_text="PAN Card Number (10 characters, e.g., ABCDE1234F)",
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$',
                message="PAN card must be 10 characters: 5 uppercase letters, 4 digits, 1 uppercase letter (e.g., ABCDE1234F)"
            )
        ]
    )
    
    pan_card_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Name as per PAN Card"
    )
    
    # --------------------
    # Aadhar Card Information
    # --------------------
    aadhar_card_number = models.CharField(
        max_length=12,
        unique=True,
        null=False,
        blank=False,
        help_text="Aadhar Card Number (12 digits)",
        validators=[
            RegexValidator(
                regex=r'^\d{12}$',
                message="Aadhar card must be exactly 12 digits"
            )
        ]
    )
    
    aadhar_card_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Name as per Aadhar Card"
    )
    
    # --------------------
    # Bank Account Information
    # --------------------
    bank_name = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        help_text="Name of the Bank"
    )
    
    account_number = models.CharField(
        max_length=50,
        null=False,
        blank=False,
        help_text="Bank Account Number",
        validators=[
            RegexValidator(
                regex=r'^\d{9,18}$',
                message="Account number must be between 9 to 18 digits"
            )
        ]
    )
    
    account_holder_name = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        help_text="Account Holder Name (as per bank records)"
    )
    
    account_type = models.CharField(
        max_length=50,
        choices=ACCOUNT_TYPE_CHOICES,
        null=False,
        blank=False,
        default='savings',
        help_text="Type of bank account"
    )
    
    ifsc_code = models.CharField(
        max_length=11,
        null=False,
        blank=False,
        help_text="IFSC Code (11 characters, e.g., HDFC0001234)",
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{4}0[A-Z0-9]{6}$',
                message="IFSC code must be 11 characters: 4 uppercase letters, 0, followed by 6 alphanumeric characters (e.g., HDFC0001234)"
            )
        ]
    )
    
    bank_address = models.TextField(
        null=False,
        blank=False,
        help_text="Complete address of the bank branch"
    )
    
    branch_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Bank Branch Name"
    )
    
    city = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        help_text="City where bank branch is located"
    )
    
    state = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        help_text="State where bank branch is located"
    )
    
    pincode = models.CharField(
        max_length=6,
        null=False,
        blank=False,
        help_text="PIN Code (6 digits)",
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message="PIN code must be exactly 6 digits"
            )
        ]
    )
    
    # --------------------
    # Additional Information
    # --------------------
    is_primary = models.BooleanField(
        default=True,
        help_text="Whether this is the primary bank account for salary payments"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this bank information is active"
    )
    
    # --------------------
    # Timestamps
    # --------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "employee_bank_info"
        verbose_name = "Employee Bank Information"
        verbose_name_plural = "Employee Bank Information"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'is_active'], name='bankinfo_emp_active_idx'),
            models.Index(fields=['id', 'employee'], name='bankinfo_id_emp_idx'),
        ]
    
    def __str__(self):
        return f"{self.employee.id} | {self.bank_name} | {self.account_number[:4]}****"
    
    def clean(self):
        """Additional validation at model level"""
        # PAN Card validation - ensure uppercase
        if self.pan_card_number:
            self.pan_card_number = self.pan_card_number.upper()
        
        # IFSC Code validation - ensure uppercase
        if self.ifsc_code:
            self.ifsc_code = self.ifsc_code.upper()
        
        # Aadhar validation - check for valid format (should not start with 0 or 1)
        if self.aadhar_card_number and len(self.aadhar_card_number) == 12:
            if self.aadhar_card_number.startswith('0') or self.aadhar_card_number.startswith('1'):
                raise ValidationError({
                    'aadhar_card_number': 'Aadhar card number cannot start with 0 or 1'
                })
        
        super().clean()
    
    def save(self, *args, **kwargs):
        """Override save to ensure clean() is called"""
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== EMPLOYEE ADVANCE ====================
class EmployeeAdvance(models.Model):
    """
    Employee Advance/Loan Model
    Stores advance requests and repayment information
    """
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('partially_paid', 'Partially Paid'),
        ('settled', 'Settled'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    
    # --------------------
    # Ownership
    # --------------------
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "user"},
        related_name="employee_advances",
        help_text="Employee who requested the advance"
    )
    
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "admin"},
        related_name="admin_advances",
        help_text="Admin who created/manages this advance"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='advances',
        help_text="Site associated with this advance"
    )
    
    created_by = models.ForeignKey(
        BaseUserModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role__in": ["admin", "organization"]},
        related_name="created_advances",
        help_text="User who created this advance"
    )
    
    # --------------------
    # Advance Details
    # --------------------
    advance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=False,
        blank=False,
        help_text="Total advance amount requested",
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    request_date = models.DateField(
        null=False,
        blank=False,
        help_text="Date when advance was requested"
    )
    
    purpose = models.TextField(
        null=True,
        blank=True,
        help_text="Purpose/reason for the advance"
    )
    
    # --------------------
    # Status
    # --------------------
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='active',
        null=False,
        blank=False,
        help_text="Current status of the advance"
    )
    
    # --------------------
    # Payment Tracking
    # --------------------
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount paid so far",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=False,
        blank=False,
        help_text="Remaining amount to be paid",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    is_settled = models.BooleanField(
        default=False,
        help_text="Whether the advance has been fully settled"
    )
    
    settlement_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when advance was fully settled"
    )
    
    # --------------------
    # Additional Information
    # --------------------
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Additional notes or comments"
    )
    
    attachment = models.FileField(
        upload_to='advance_attachments/',
        null=True,
        blank=True,
        help_text="Supporting documents (if any)"
    )
    
    # --------------------
    # Timestamps
    # --------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "employee_advance"
        verbose_name = "Employee Advance"
        verbose_name_plural = "Employee Advances"
        ordering = ['-request_date', '-created_at']
        indexes = [
            models.Index(fields=['admin', 'status', 'request_date'], name='advance_adm_status_date_idx'),
            models.Index(fields=['employee', 'status', 'request_date'], name='advance_emp_status_date_idx'),
            models.Index(fields=['id', 'admin'], name='advance_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'status', 'request_date'], name='advance_site_adm_st_dt_idx'),
        ]
    
    def __str__(self):
        return f"{self.employee.id} | ₹{self.advance_amount} | {self.get_status_display()}"
    
    def clean(self):
        """Additional validation at model level"""
        from django.core.exceptions import ValidationError
        
        # Ensure remaining_amount is calculated correctly
        if self.advance_amount and self.paid_amount is not None:
            self.remaining_amount = self.advance_amount - self.paid_amount
            if self.remaining_amount < Decimal('0.00'):
                raise ValidationError({
                    'paid_amount': 'Paid amount cannot exceed advance amount'
                })
        
        # If settled, ensure paid_amount equals advance_amount
        if self.is_settled and self.advance_amount and self.paid_amount != self.advance_amount:
            raise ValidationError({
                'is_settled': 'Cannot mark as settled until full amount is paid'
            })
        
        super().clean()
    
    def save(self, *args, **kwargs):
        """Override save to ensure calculations and clean() are called"""
        # Calculate remaining amount
        if self.advance_amount and self.paid_amount is not None:
            self.remaining_amount = self.advance_amount - self.paid_amount
        
        # Update is_settled status
        if self.advance_amount and self.paid_amount:
            self.is_settled = (self.paid_amount >= self.advance_amount)
            if self.is_settled and not self.settlement_date:
                from django.utils import timezone
                self.settlement_date = timezone.now().date()
        
        # Update status based on payment
        if self.status in ['active', 'partially_paid'] and self.paid_amount > Decimal('0.00'):
            if self.is_settled:
                self.status = 'settled'
            elif self.paid_amount < self.advance_amount:
                self.status = 'partially_paid'
            elif self.status == 'partially_paid' and self.paid_amount >= self.advance_amount:
                self.status = 'settled'
        
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== EMPLOYEE CUSTOM MONTHLY EARNINGS ====================
class EmployeeCustomMonthlyEarning(models.Model):
    """
    Employee Custom Monthly Earnings Model
    Used for uploading/adjusting monthly earnings
    """
    
    id = models.BigAutoField(primary_key=True)
    
    # --------------------
    # Ownership
    # --------------------
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "user"},
        related_name="employee_earnings",
        help_text="Employee for whom earnings are recorded"
    )
    
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "admin"},
        related_name="admin_earnings",
        help_text="Admin who manages this record"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='earnings',
        help_text="Site associated with this earning"
    )
    
    # --------------------
    # Period
    # --------------------
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=False,
        blank=False,
        help_text="Month (1-12) for which earnings are recorded"
    )
    
    year = models.IntegerField(
        null=False,
        blank=False,
        help_text="Year for which earnings are recorded"
    )
    
    # --------------------
    # Earnings Fields
    # --------------------
    overtime_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Overtime Pay",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    incentives = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Incentives",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    impact_award = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Impact Award",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    bonus = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Bonus",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    expenses = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Expenses/Reimbursements",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    leave_encashment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Leave Encashment",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    adjustments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Adjustments",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    arrears = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Arrears",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    performance_allowance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Performance Allowance",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    other_allowances = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Other Allowances",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # --------------------
    # Additional Information
    # --------------------
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Additional notes or comments"
    )
    
    # --------------------
    # Timestamps
    # --------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "employee_custom_monthly_earning"
        verbose_name = "Employee Custom Monthly Earning"
        verbose_name_plural = "Employee Custom Monthly Earnings"
        unique_together = ("employee", "month", "year")
        ordering = ['-year', '-month', '-created_at']
        indexes = [
            models.Index(fields=['admin', 'year', 'month'], name='earning_adm_ym_idx'),
            models.Index(fields=['employee', 'year', 'month'], name='earning_emp_ym_idx'),
            models.Index(fields=['id', 'admin'], name='earning_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'year', 'month'], name='earning_site_adm_ym_idx'),
        ]
    
    def __str__(self):
        return f"{self.employee.id} | {self.month}/{self.year} | Total Earnings: ₹{self.total_earnings}"
    
    @property
    def total_earnings(self):
        """Calculate total earnings"""
        return (
            self.overtime_pay + self.incentives + self.impact_award + 
            self.bonus + self.expenses + self.leave_encashment + 
            self.adjustments + self.arrears + self.performance_allowance + 
            self.other_allowances
        )


# ==================== EMPLOYEE CUSTOM MONTHLY DEDUCTIONS ====================
class EmployeeCustomMonthlyDeduction(models.Model):
    """
    Employee Custom Monthly Deductions Model
    Used for uploading/adjusting monthly deductions
    """
    
    id = models.BigAutoField(primary_key=True)
    
    # --------------------
    # Ownership
    # --------------------
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "user"},
        related_name="employee_deductions",
        help_text="Employee for whom deductions are recorded"
    )
    
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "admin"},
        related_name="admin_deductions",
        help_text="Admin who manages this record"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deductions',
        help_text="Site associated with this deduction"
    )
    
    # --------------------
    # Period
    # --------------------
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=False,
        blank=False,
        help_text="Month (1-12) for which deductions are recorded"
    )
    
    year = models.IntegerField(
        null=False,
        blank=False,
        help_text="Year for which deductions are recorded"
    )
    
    # --------------------
    # Deductions Fields
    # --------------------
    income_tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Income Tax (TDS)",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    advance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Advance Deduction",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    lwf = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Labour Welfare Fund (LWF)",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    uniform = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Uniform Charges",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    canteen_food = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Canteen/Food Charges",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    late_mark_fine = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Late Mark Fine",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    penalty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Penalty",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    employee_welfare_fund = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Employee Welfare Fund",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    other_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Other Deductions",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # --------------------
    # Additional Information
    # --------------------
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Additional notes or comments"
    )
    
    # --------------------
    # Timestamps
    # --------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "employee_custom_monthly_deduction"
        verbose_name = "Employee Custom Monthly Deduction"
        verbose_name_plural = "Employee Custom Monthly Deductions"
        unique_together = ("employee", "month", "year")
        ordering = ['-year', '-month', '-created_at']
        indexes = [
            models.Index(fields=['admin', 'year', 'month'], name='deduction_adm_ym_idx'),
            models.Index(fields=['employee', 'year', 'month'], name='deduction_emp_ym_idx'),
            models.Index(fields=['id', 'admin'], name='deduction_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'year', 'month'], name='deduction_site_adm_ym_idx'),
        ]
    
    def __str__(self):
        return f"{self.employee.id} | {self.month}/{self.year} | Total Deductions: ₹{self.total_deductions}"
    

# ==================== GENERATED PAYROLL RECORD ====================
class GeneratedPayrollRecord(models.Model):
    """
    Generated Payroll Record Model
    Stores complete payroll calculation for an employee for a specific month/year
    Generated from attendance sheet with payable days
    """
    
    id = models.BigAutoField(primary_key=True)
    
    # --------------------
    # Ownership
    # --------------------
    employee = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "user"},
        related_name="generated_payroll_records",
        help_text="Employee for whom payroll is generated"
    )
    
    admin = models.ForeignKey(
        BaseUserModel,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "admin"},
        related_name="admin_generated_payroll_records",
        help_text="Admin who generated this payroll"
    )
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_payroll_records',
        help_text="Site associated with this payroll record"
    )
    
    # --------------------
    # Period
    # --------------------
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=False,
        blank=False,
        help_text="Month (1-12) for which payroll is generated"
    )
    
    year = models.IntegerField(
        null=False,
        blank=False,
        help_text="Year for which payroll is generated"
    )
    
    # --------------------
    # Attendance Data (from Excel)
    # --------------------
    payable_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Payable days from attendance sheet",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    total_days_in_month = models.IntegerField(
        default=30,
        help_text="Total days in the month"
    )
    
    # --------------------
    # Salary Components (from EmployeePayrollConfig)
    # --------------------
    gross_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly gross salary"
    )
    
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Basic salary (calculated based on payable days)"
    )
    
    # --------------------
    # Earnings Breakdown (stored as list of components)
    # --------------------
    earnings = models.JSONField(
        default=list,
        blank=True,
        help_text="List of earnings components. Each item: {'name': str, 'amount': Decimal, 'type': str}"
    )
    
    # --------------------
    # Deductions Breakdown (stored as list of components)
    # --------------------
    deductions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of deductions components. Each item: {'name': str, 'amount': Decimal, 'type': str}"
    )
    
    # --------------------
    # Totals
    # --------------------
    total_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total Earnings (Basic + Allowances + Custom Earnings)"
    )
    
    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total Deductions (Statutory + Custom Deductions)"
    )
    
    net_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Net Pay (Total Earnings - Total Deductions)"
    )
    
    # --------------------
    # Additional Information
    # --------------------
    payslip_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text="Auto-generated payslip number"
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes or remarks"
    )
    
    # Store full calculation breakdown as JSON for reference
    calculation_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete calculation breakdown in JSON format"
    )
    
    # Reference to related records
    payroll_config = models.ForeignKey(
        EmployeePayrollConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_payroll_records",
        help_text="Reference to employee payroll config used"
    )
    
    custom_earnings_record = models.ForeignKey(
        EmployeeCustomMonthlyEarning,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_payroll_records",
        help_text="Reference to custom earnings record"
    )
    
    custom_deductions_record = models.ForeignKey(
        EmployeeCustomMonthlyDeduction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_payroll_records",
        help_text="Reference to custom deductions record"
    )
    
    # --------------------
    # Timestamps
    # --------------------
    generated_at = models.DateTimeField(auto_now_add=True, help_text="When payroll was generated")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")
    
    class Meta:
        db_table = "generated_payroll_record"
        verbose_name = "Generated Payroll Record"
        verbose_name_plural = "Generated Payroll Records"
        unique_together = ("employee", "month", "year", "admin")
        ordering = ['-year', '-month', '-generated_at']
        indexes = [
            models.Index(fields=['employee', 'month', 'year'], name='payroll_emp_ym_idx'),
            models.Index(fields=['admin', 'month', 'year'], name='payroll_adm_ym_idx'),
            models.Index(fields=['admin', 'employee', 'year', 'month'], name='payroll_adm_emp_ym_idx'),
            models.Index(fields=['id', 'admin'], name='payroll_id_adm_idx'),
            # Site filtering optimization - O(1) queries
            models.Index(fields=['site', 'admin', 'month', 'year'], name='payroll_site_adm_ym_idx'),
        ]
    
    def __str__(self):
        return f"{self.employee.id} | {self.month}/{self.year} | Net Pay: ₹{self.net_pay}"
    
    def save(self, *args, **kwargs):
        # Auto-generate payslip number if not provided
        if not self.payslip_number:
            from datetime import datetime
            month_name = datetime(self.year, self.month, 1).strftime('%b').upper()
            prefix = f"PAY-{self.year}-{month_name}-"
            last_record = GeneratedPayrollRecord.objects.filter(
                payslip_number__startswith=prefix
            ).order_by('-id').first()
            
            if last_record and last_record.payslip_number:
                try:
                    last_num = int(last_record.payslip_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.payslip_number = f"{prefix}{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    @property
    def total_earnings_from_list(self):
        """Calculate total earnings from earnings list"""
        if not self.earnings:
            return Decimal('0.00')
        total = Decimal('0.00')
        for item in self.earnings:
            if isinstance(item, dict) and 'amount' in item:
                try:
                    total += Decimal(str(item['amount']))
                except (ValueError, TypeError):
                    pass
        return total
    
    @property
    def total_deductions_from_list(self):
        """Calculate total deductions from deductions list"""
        if not self.deductions:
            return Decimal('0.00')
        total = Decimal('0.00')
        for item in self.deductions:
            if isinstance(item, dict) and 'amount' in item:
                try:
                    total += Decimal(str(item['amount']))
                except (ValueError, TypeError):
                    pass
        return total

