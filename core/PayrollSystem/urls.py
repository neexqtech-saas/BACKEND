"""
Payroll System URLs
"""
from django.urls import path
from .views import (
    PayslipGeneratorAPIView,
    ProfessionalTaxRuleAPIView,
    OrganizationPayrollSettingsAPIView,
    SalaryStructureUnifiedAPIView,
    EmployeePayrollConfigAPIView,
    EmployeeBankInfoAPIView,
    EmployeeAdvanceAPIView,
    EmployeeEarningsExcelAPIView,
    EmployeeDeductionsExcelAPIView,
    DemoAttendanceSheetDownloadAPIView,
    GeneratePayrollFromAttendanceAPIView,
    GeneratePayslipFromPayrollRecordAPIView,
    PayslipListView,
)

urlpatterns = [
    # Payslip Generator Routes
    path('payslip-generator/<uuid:site_id>/', PayslipGeneratorAPIView.as_view(), name='payslip-generator-list-create'),
    path('payslip-generator/<uuid:site_id>/<int:pk>/', PayslipGeneratorAPIView.as_view(), name='payslip-generator-detail'),
    
    # Professional Tax Rule Routes
    path('pt-rules/', ProfessionalTaxRuleAPIView.as_view(), name='professional-tax-rules'),
    
    # Organization Payroll Settings Routes
    path('payroll-settings/<uuid:org_id>/', OrganizationPayrollSettingsAPIView.as_view(), name='organization-payroll-settings'),
    
    # Salary Structure Unified CRUD API
    path('salary-structure/<uuid:org_id>/', SalaryStructureUnifiedAPIView.as_view(), name='salary-structure-unified'),
    
    # Employee Payroll Config Unified CRUD API
    path('employee-payroll-config/<uuid:site_id>/', EmployeePayrollConfigAPIView.as_view(), name='employee-payroll-config-list-create'),
    path('employee-payroll-config/<uuid:site_id>/employee/<uuid:employee_id>/', EmployeePayrollConfigAPIView.as_view(), name='employee-payroll-config-by-employee'),
    path('employee-payroll-config/<uuid:site_id>/<int:pk>/', EmployeePayrollConfigAPIView.as_view(), name='employee-payroll-config-detail'),
    
    # Employee Bank Info CRUD API
    path('employee-bank-info/<uuid:site_id>/', EmployeeBankInfoAPIView.as_view(), name='employee-bank-info-list-create'),
    path('employee-bank-info/<uuid:site_id>/<int:pk>/', EmployeeBankInfoAPIView.as_view(), name='employee-bank-info-detail'),
    
    # Employee Advance CRUD API
    path('employee-advance/<uuid:site_id>/', EmployeeAdvanceAPIView.as_view(), name='employee-advance-list-create'),
    path('employee-advance/<uuid:site_id>/<int:pk>/', EmployeeAdvanceAPIView.as_view(), name='employee-advance-detail'),
    
    # Employee Earnings Excel API
    path('employee-earnings-excel/<uuid:site_id>/', EmployeeEarningsExcelAPIView.as_view(), name='employee-earnings-excel'),
    
    # Employee Deductions Excel API
    path('employee-deductions-excel/<uuid:site_id>/', EmployeeDeductionsExcelAPIView.as_view(), name='employee-deductions-excel'),
    
    # Demo Attendance Sheet Download API
    path('demo-attendance-sheet/<uuid:site_id>/', DemoAttendanceSheetDownloadAPIView.as_view(), name='demo-attendance-sheet-download'),
    
    # Generate Payroll from Attendance Sheet API
    path('generate-payroll-from-attendance/<uuid:site_id>/', GeneratePayrollFromAttendanceAPIView.as_view(), name='generate-payroll-from-attendance'),
    
    # Generate Payslip from Payroll Record API - Generates payslips for all employees
    path('generate-payslip-from-payroll/<uuid:site_id>/', GeneratePayslipFromPayrollRecordAPIView.as_view(), name='generate-payslip-from-payroll'),
    
    # Payslip List API
    path('payslip-list/<uuid:site_id>/', PayslipListView.as_view(), name='payslip-list'),
]
