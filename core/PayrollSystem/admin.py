from django.contrib import admin
from .models import PayslipGenerator, ProfessionalTaxRule, OrganizationPayrollSettings


@admin.register(PayslipGenerator)
class PayslipGeneratorAdmin(admin.ModelAdmin):
    list_display = ['payslip_number', 'employee_name', 'month', 'year', 'net_pay', 'created_at']
    list_filter = ['year', 'month', 'template', 'created_at']
    search_fields = ['payslip_number', 'employee_name', 'employee_id']
    readonly_fields = ['payslip_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(ProfessionalTaxRule)
class ProfessionalTaxRuleAdmin(admin.ModelAdmin):
    list_display = ['state_name', 'salary_from', 'salary_to', 'tax_amount', 'applicable_month', 'is_active', 'created_at']
    list_filter = ['state_name', 'is_active', 'applicable_month', 'created_at']
    search_fields = ['state_name']
    readonly_fields = ['created_at']
    ordering = ['state_name', 'salary_from']


@admin.register(OrganizationPayrollSettings)
class OrganizationPayrollSettingsAdmin(admin.ModelAdmin):
    list_display = ['organization', 'pf_enabled', 'esi_enabled', 'gratuity_enabled', 'pt_enabled', 'created_at']
    list_filter = ['pf_enabled', 'esi_enabled', 'gratuity_enabled', 'pt_enabled', 'created_at']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Organization', {
            'fields': ('organization',)
        }),
        ('Provident Fund (PF)', {
            'fields': ('pf_enabled', 'pf_employee_percentage', 'pf_employer_percentage', 'pf_wage_limit')
        }),
        ('Employee State Insurance (ESI)', {
            'fields': ('esi_enabled', 'esi_employee_percentage', 'esi_employer_percentage', 'esi_wage_limit')
        }),
        ('Gratuity', {
            'fields': ('gratuity_enabled', 'gratuity_percentage')
        }),
        ('Professional Tax (TEMPORARY)', {
            'fields': ('pt_enabled', 'pt_fixed'),
            'description': 'TEMPORARY: Will be replaced by state-wise PT rules in future versions'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
