"""
Payroll System Utility Functions
Optimized calculation and helper functions
"""
from decimal import Decimal
from django.db.models import Prefetch, Q
from .models import (
    ProfessionalTaxRule,
    OrganizationPayrollSettings,
    SalaryStructureItem,
    SalaryComponent,
    EmployeePayrollConfig,
    SalaryStructure,
)
from AuthN.models import BaseUserModel, UserProfile, AdminProfile


# ==================== STATUTORY CALCULATION FUNCTIONS ====================

def calculate_pf_employee(gross_salary, payroll_settings, pf_applicable_override):
    """Calculate PF Employee contribution - O(1) complexity"""
    if not payroll_settings or not payroll_settings.pf_enabled:
        return Decimal('0.00')
    if pf_applicable_override is False:
        return Decimal('0.00')
    pf_base = min(gross_salary, payroll_settings.pf_wage_limit)
    pf_amount = (pf_base * payroll_settings.pf_employee_percentage) / Decimal('100')
    return round(pf_amount, 2)


def calculate_pf_employer(gross_salary, payroll_settings, pf_applicable_override):
    """Calculate PF Employer contribution - O(1) complexity"""
    if not payroll_settings or not payroll_settings.pf_enabled:
        return Decimal('0.00')
    if pf_applicable_override is False:
        return Decimal('0.00')
    pf_base = min(gross_salary, payroll_settings.pf_wage_limit)
    pf_amount = (pf_base * payroll_settings.pf_employer_percentage) / Decimal('100')
    return round(pf_amount, 2)


def calculate_esi_employee(gross_salary, payroll_settings, esi_applicable_override):
    """Calculate ESI Employee contribution - O(1) complexity"""
    if not payroll_settings or not payroll_settings.esi_enabled:
        return Decimal('0.00')
    if esi_applicable_override is False:
        return Decimal('0.00')
    if gross_salary > payroll_settings.esi_wage_limit:
        return Decimal('0.00')
    esi_amount = (gross_salary * payroll_settings.esi_employee_percentage) / Decimal('100')
    return round(esi_amount, 2)


def calculate_esi_employer(gross_salary, payroll_settings, esi_applicable_override):
    """Calculate ESI Employer contribution - O(1) complexity"""
    if not payroll_settings or not payroll_settings.esi_enabled:
        return Decimal('0.00')
    if esi_applicable_override is False:
        return Decimal('0.00')
    if gross_salary > payroll_settings.esi_wage_limit:
        return Decimal('0.00')
    esi_amount = (gross_salary * payroll_settings.esi_employer_percentage) / Decimal('100')
    return round(esi_amount, 2)


def calculate_pt(gross_salary, employee_state, effective_month, payroll_settings, pt_applicable_override, pt_rules_cache=None):
    """
    Calculate Professional Tax - O(n) where n is number of rules for state
    Optimized with caching for batch operations
    """
    if not payroll_settings or not payroll_settings.pt_enabled:
        return Decimal('0.00')
    if pt_applicable_override is False:
        return Decimal('0.00')
    if not employee_state:
        return Decimal('200.00')  # Default PT if state not set
    
    # Use cached rules if provided (for batch operations)
    if pt_rules_cache is not None:
        pt_rules = pt_rules_cache.get(employee_state, [])
    else:
        # Single query - fetch all rules for state
        pt_rules = list(ProfessionalTaxRule.objects.filter(
            state_name=employee_state,
            is_active=True
        ).order_by('salary_from'))
    
    # Find matching rule - O(n) but n is typically small (< 10 rules per state)
    for rule in pt_rules:
        # Handle both model instances and dictionaries (from cache)
        if isinstance(rule, dict):
            applicable_month = rule.get('applicable_month')
            salary_from = rule.get('salary_from')
            salary_to = rule.get('salary_to')
            tax_amount = rule.get('tax_amount')
        else:
            applicable_month = rule.applicable_month
            salary_from = rule.salary_from
            salary_to = rule.salary_to
            tax_amount = rule.tax_amount
        
        if applicable_month and applicable_month != effective_month:
            continue
        if gross_salary >= salary_from:
            if salary_to is None or gross_salary <= salary_to:
                return tax_amount
    
    # Default PT if no rule matches
    return Decimal('200.00')


def calculate_gratuity(basic_salary, payroll_settings, gratuity_applicable_override):
    """Calculate Gratuity - O(1) complexity"""
    if not payroll_settings or not payroll_settings.gratuity_enabled:
        return Decimal('0.00')
    if gratuity_applicable_override is False:
        return Decimal('0.00')
    gratuity_amount = (basic_salary * payroll_settings.gratuity_percentage) / Decimal('100')
    return round(gratuity_amount, 2)


# ==================== COMPONENT MATCHING HELPERS ====================

def is_employee_component(component_code, component_name):
    """Check if component is employee type - O(1) complexity"""
    code_upper = component_code.upper()
    name_upper = component_name.upper()
    return (
        'EMPLOYEE' in name_upper or
        ('EMP' in code_upper and 'EMPR' not in code_upper) or
        code_upper.endswith('_EMP') or
        code_upper in ('ESIC_EMP', 'ESI_EMP', 'PF_EMP')
    )


def is_employer_component(component_code, component_name):
    """Check if component is employer type - O(1) complexity"""
    code_upper = component_code.upper()
    name_upper = component_name.upper()
    return (
        'EMPLOYER' in name_upper or
        'EMPR' in code_upper or
        code_upper.endswith('_EMPR') or
        code_upper in ('ESIC_EMPR', 'ESI_EMPR', 'PF_EMPR')
    )


def is_basic_component(component_code, component_name):
    """Check if component is BASIC - O(1) complexity"""
    code_upper = component_code.upper()
    name_upper = component_name.upper()
    return code_upper == 'BASIC' or 'BASIC' in name_upper

def is_da_component(component_code, component_name):
    """Check if component is DA (Dearness Allowance) - O(1) complexity"""
    code_upper = component_code.upper()
    name_upper = component_name.upper()
    return code_upper == 'DA' or 'DA' in name_upper or 'DEARNESS' in name_upper


def is_special_allowance_component(component_code, component_name=None):
    """Check if component is SPECIAL_ALLOWANCE - O(1) complexity"""
    code_upper = component_code.upper()
    if 'SPECIAL' in code_upper:
        return True
    if component_name:
        return 'SPECIAL' in component_name.upper()
    return False


# ==================== PAYROLL BREAKDOWN CALCULATION ====================

def calculate_payroll_breakdown_optimized(
    config,
    structure_items,
    payroll_settings,
    employee_state,
    pt_rules_cache=None
):
    """
    Optimized payroll breakdown calculation
    No queries inside loops - all data prefetched
    O(n) complexity where n is number of structure items
    """
    # Convert yearly to monthly
    gross_salary = config.gross_salary / Decimal('12')
    gross_salary = round(gross_salary, 2)
    
    earnings = []
    deductions = []
    component_amounts = {}
    basic_salary_amount = Decimal('0.00')
    gratuity_item = None
    special_allowance_index = None
    
    # Pre-build lookup dictionaries for O(1) access
    component_lookup = {}  # component_code -> component_data
    calculation_base_lookup = {}  # component_code -> base_component_code
    
    # First pass: Build lookup dictionaries and find special components
    for idx, item in enumerate(structure_items):
        component = item.component
        component_code = component.code
        component_lookup[component_code] = {
            'item': item,
            'component': component,
            'index': idx
        }
        if item.calculation_base:
            calculation_base_lookup[component_code] = item.calculation_base.code
        
        # Find gratuity and special allowance in first pass
        if (item.calculation_type == 'auto' and 
            component.statutory_type == 'GRATUITY'):
            gratuity_item = item
        
        if is_special_allowance_component(component_code, component.name):
            special_allowance_index = idx
    
    # Second pass: Calculate all components
    # First, calculate BASIC component if it exists (needed as default base for percentage calculations)
    basic_component_code = None
    for component_code, data in component_lookup.items():
        item = data['item']
        component = data['component']
        component_name = component.name
        if is_basic_component(component_code, component_name):
            basic_component_code = component_code
            # Calculate basic first
            if item.calculation_type == 'fixed':
                basic_salary_amount = item.value or Decimal('0.00')
            elif item.calculation_type == 'percentage':
                # Basic can be percentage of gross (calculate it)
                percentage = item.value or Decimal('0.00')
                basic_salary_amount = (gross_salary * percentage) / Decimal('100')
                basic_salary_amount = round(basic_salary_amount, 2)
            else:
                # For auto/other types, will be calculated later
                basic_salary_amount = Decimal('0.00')
            
            component_amounts[component_code] = basic_salary_amount
            break
    
    # Calculate DA component early (needed for PF calculation)
    da_component_code = None
    for component_code, data in component_lookup.items():
        item = data['item']
        component = data['component']
        component_name = component.name
        if is_da_component(component_code, component_name) and component_code not in component_amounts:
            da_component_code = component_code
            # Calculate DA
            if item.calculation_type == 'fixed':
                da_amount = item.value or Decimal('0.00')
            elif item.calculation_type == 'percentage':
                # DA should use basic_salary as base (all earnings calculated on basic)
                percentage = item.value or Decimal('0.00')
                da_base = basic_salary_amount if basic_salary_amount > 0 else gross_salary
                da_amount = (da_base * percentage) / Decimal('100')
                da_amount = round(da_amount, 2)
            else:
                da_amount = Decimal('0.00')
            
            component_amounts[component_code] = da_amount
            break
    
    # Now calculate all components
    for component_code, data in component_lookup.items():
        item = data['item']
        component = data['component']
        component_name = component.name
        component_type = component.component_type
        amount = Decimal('0.00')
        
        # If basic or DA already calculated, use that value
        if component_code == basic_component_code and component_code in component_amounts:
            amount = component_amounts[component_code]
        elif component_code == da_component_code and component_code in component_amounts:
            amount = component_amounts[component_code]
        # Handle AUTO (statutory) components
        elif item.calculation_type == 'auto' and component.statutory_type:
            if not payroll_settings:
                continue
            
            statutory_type = component.statutory_type
            
            if statutory_type == 'PF':
                if is_employee_component(component_code, component_name):
                    # PF should be calculated on (BASIC + DA) if DA exists, else on BASIC only
                    pf_base_salary = basic_salary_amount if basic_salary_amount > 0 else gross_salary
                    
                    # Check if DA component exists and add it to PF base
                    da_amount = Decimal('0.00')
                    for comp_code, comp_data in component_lookup.items():
                        comp = comp_data['component']
                        if is_da_component(comp_code, comp.name) and comp_code in component_amounts:
                            da_amount = component_amounts[comp_code]
                            break
                    
                    # PF base = BASIC + DA (if DA exists)
                    pf_base_salary = pf_base_salary + da_amount
                    
                    amount = calculate_pf_employee(pf_base_salary, payroll_settings, config.pf_applicable)
                elif is_employer_component(component_code, component_name):
                    amount = Decimal('0.00')
            
            elif statutory_type == 'ESI':
                if is_employee_component(component_code, component_name):
                    amount = calculate_esi_employee(gross_salary, payroll_settings, config.esi_applicable)
                elif is_employer_component(component_code, component_name):
                    amount = Decimal('0.00')
                else:
                    # Fallback: assume employee
                    amount = calculate_esi_employee(gross_salary, payroll_settings, config.esi_applicable)
            
            elif statutory_type == 'PT':
                if employee_state:
                    amount = calculate_pt(
                        gross_salary, employee_state, config.effective_month,
                        payroll_settings, config.pt_applicable, pt_rules_cache
                    )
                else:
                    amount = Decimal('0.00')
            
            elif statutory_type == 'GRATUITY':
                # Skip for now - will process after basic salary is known
                continue
        
        elif item.calculation_type == 'fixed':
            amount = item.value or Decimal('0.00')
        
        elif item.calculation_type == 'percentage':
            base_code = calculation_base_lookup.get(component_code)
            if base_code:
                # Use specified calculation base
                base_amount = component_amounts.get(base_code, gross_salary)
            else:
                # No calculation base specified - ALL earnings use basic_salary as base
                if basic_component_code and basic_component_code in component_amounts:
                    base_amount = component_amounts[basic_component_code]
                else:
                    # Fallback to gross if basic not available
                    base_amount = gross_salary
            percentage = item.value or Decimal('0.00')
            amount = (base_amount * percentage) / Decimal('100')
            amount = round(amount, 2)
        
        # Store component amount
        is_statutory = (item.calculation_type == 'auto' and component.statutory_type)
        should_store = (
            item.calculation_type == 'fixed' or
            item.calculation_type == 'percentage' or
            (is_statutory and (amount > 0 or component.statutory_type in ['ESI', 'PF', 'PT']))
        )
        
        if should_store:
            component_amounts[component_code] = amount
            
            # Track basic salary
            if is_basic_component(component_code, component_name):
                basic_salary_amount = amount
            
            # Add to earnings or deductions
            if amount > 0 or component_type == 'earning':
                if not is_employer_component(component_code, component_name):
                    component_data = {
                        'component': component_code,
                        'amount': float(amount)
                    }
                    if component_type == 'earning':
                        earnings.append(component_data)
                    else:
                        deductions.append(component_data)
    
    # Calculate GRATUITY after basic salary is known
    if payroll_settings and basic_salary_amount > 0 and gratuity_item:
        gratuity_amount = calculate_gratuity(
            basic_salary_amount, payroll_settings, config.gratuity_applicable
        )
        if gratuity_amount > 0:
            component_code = gratuity_item.component.code
            component_amounts[component_code] = gratuity_amount
            deductions.append({
                'component': component_code,
                'amount': float(gratuity_amount)
            })
    
    # Calculate total earnings
    total_earnings = sum(Decimal(str(e['amount'])) for e in earnings)
    
    # Handle SPECIAL_ALLOWANCE adjustment
    remaining = gross_salary - total_earnings
    if remaining != 0:
        # Find special allowance in earnings list (O(n) but n is small)
        special_earning = None
        for earning in earnings:
            if is_special_allowance_component(earning['component']):
                special_earning = earning
                break
        
        if special_earning:
            new_amount = max(Decimal('0.00'), Decimal(str(special_earning['amount'])) + remaining)
            special_earning['amount'] = float(new_amount)
        elif remaining > 0:
            earnings.append({
                'component': 'SPECIAL_ALLOWANCE',
                'amount': float(remaining)
            })
        
        total_earnings = gross_salary
    
    # Filter employer components from deductions (already filtered during addition, but safety check)
    filtered_deductions = [
        d for d in deductions
        if not is_employer_component(d['component'], '')
    ]
    
    # Calculate totals
    total_deductions = sum(Decimal(str(d['amount'])) for d in filtered_deductions)
    net_pay = total_earnings - total_deductions
    
    return {
        'earnings': earnings,
        'deductions': filtered_deductions,
        'total_earnings': round(total_earnings, 2),
        'total_deductions': round(total_deductions, 2),
        'net_pay': round(net_pay, 2)
    }


# ==================== BATCH DATA FETCHING ====================

def prefetch_payroll_data(configs):
    """
    Prefetch all related data for batch operations
    Returns: (structure_items_map, payroll_settings_map, employee_states_map, pt_rules_cache)
    """
    # Get unique structures and organizations
    structure_ids = set()
    organization_ids = set()
    employee_ids = set()
    
    for config in configs:
        structure_ids.add(config.salary_structure_id)
        organization_ids.add(config.salary_structure.organization_id)
        employee_ids.add(config.employee_id)
    
    # Prefetch structure items for all structures
    structure_items_map = {}
    structure_items_qs = SalaryStructureItem.objects.filter(
        structure_id__in=structure_ids
    ).select_related('component', 'calculation_base').order_by('order', 'id')
    
    for item in structure_items_qs:
        structure_id = item.structure_id
        if structure_id not in structure_items_map:
            structure_items_map[structure_id] = []
        structure_items_map[structure_id].append(item)
    
    # Prefetch payroll settings for all organizations
    payroll_settings_map = {}
    payroll_settings_qs = OrganizationPayrollSettings.objects.filter(
        organization_id__in=organization_ids
    ).select_related('organization')
    
    for settings in payroll_settings_qs:
        payroll_settings_map[settings.organization_id] = settings
    
    # Prefetch employee states
    employee_states_map = {}
    employee_profiles = UserProfile.objects.filter(
        user_id__in=employee_ids
    ).values('user_id', 'state')
    
    for profile in employee_profiles:
        employee_states_map[profile['user_id']] = profile.get('state')
    
    # Prefetch PT rules for all unique states
    unique_states = set(employee_states_map.values())
    unique_states.discard(None)
    
    pt_rules_cache = {}
    if unique_states:
        pt_rules_qs = ProfessionalTaxRule.objects.filter(
            state_name__in=unique_states,
            is_active=True
        ).order_by('state_name', 'salary_from')
        
        for rule in pt_rules_qs:
            state = rule.state_name
            if state not in pt_rules_cache:
                pt_rules_cache[state] = []
            pt_rules_cache[state].append(rule)
    
    return structure_items_map, payroll_settings_map, employee_states_map, pt_rules_cache


# ==================== STATUTORY COMPONENTS OPTIMIZATION ====================

def get_statutory_components_map(organization):
    """
    Fetch all statutory components for an organization in one query
    Returns: dict mapping component_code -> SalaryComponent
    """
    components = SalaryComponent.objects.filter(
        organization=organization,
        statutory_type__isnull=False
    ).select_related('organization')
    
    return {comp.code: comp for comp in components}


def build_statutory_components_list(payroll_settings, components_map):
    """
    Build statutory components list from payroll settings and prefetched components
    No database queries - uses prefetched components_map
    """
    if not payroll_settings:
        return []
    
    statutory_list = []
    organization = payroll_settings.organization
    
    # PF Components (if enabled)
    if payroll_settings.pf_enabled:
        pf_emp = components_map.get('PF_EMP')
        if pf_emp:
            statutory_list.append({
                'component': pf_emp.code,
                'label': pf_emp.name,
                'statutory_type': 'PF',
                'component_type': pf_emp.component_type,
                'enabled': True,
                'display_value': f"{payroll_settings.pf_employee_percentage}%",
            })
        
        pf_empr = components_map.get('PF_EMPR')
        if pf_empr:
            statutory_list.append({
                'component': pf_empr.code,
                'label': pf_empr.name,
                'statutory_type': 'PF',
                'component_type': pf_empr.component_type,
                'enabled': True,
                'display_value': f"{payroll_settings.pf_employer_percentage}%",
            })
    
    # ESIC Components (if enabled)
    if payroll_settings.esi_enabled:
        esic_emp = components_map.get('ESIC_EMP')
        if esic_emp:
            statutory_list.append({
                'component': esic_emp.code,
                'label': esic_emp.name,
                'statutory_type': 'ESI',
                'component_type': esic_emp.component_type,
                'enabled': True,
                'display_value': f"{payroll_settings.esi_employee_percentage}%",
            })
        
        esic_empr = components_map.get('ESIC_EMPR')
        if esic_empr:
            statutory_list.append({
                'component': esic_empr.code,
                'label': esic_empr.name,
                'statutory_type': 'ESI',
                'component_type': esic_empr.component_type,
                'enabled': True,
                'display_value': f"{payroll_settings.esi_employer_percentage}%",
            })
    
    # PT (if enabled)
    if payroll_settings.pt_enabled:
        pt = components_map.get('PT')
        if pt:
            statutory_list.append({
                'component': pt.code,
                'label': pt.name,
                'statutory_type': 'PT',
                'component_type': pt.component_type,
                'enabled': True,
                'display_value': "Auto (State-wise)",
            })
    
    # Gratuity (if enabled)
    if payroll_settings.gratuity_enabled:
        gratuity = components_map.get('GRATUITY')
        if gratuity:
            statutory_list.append({
                'component': gratuity.code,
                'label': gratuity.name,
                'statutory_type': 'GRATUITY',
                'component_type': gratuity.component_type,
                'enabled': True,
                'display_value': f"{payroll_settings.gratuity_percentage}%",
            })
    
    return statutory_list


# ==================== EMPLOYEE PAYROLL DETAILS AGGREGATION ====================

def get_all_employee_payroll_details(admin_id, month, year, employee_id=None):
    """
    Get comprehensive payroll details for all employees under an admin for a specific month/year
    If employee is provided, returns only that employee's details
    
    Args:
        admin_id (str): Admin UUID
        month (int): Month (1-12)
        year (int): Year
        employee_id (str, optional): Employee UUID - if provided, returns only this employee's details
        
    Returns:
        dict: {
            'employees': [
                {
                    'employee_id': str,
                    'employee_name': str,
                    'custom_employee_id': str,
                    'designation': str,
                    'state': str,
                    'city': str,
                    'assigned_shifts': [...],
                    'payroll_config': {
                        'config_id': int,
                        'gross_salary': Decimal,
                        'effective_month': int,
                        'effective_year': int,
                        'salary_structure_id': int,
                        'salary_structure_name': str,
                        'pf_applicable': bool/None,
                        'esi_applicable': bool/None,
                        'pt_applicable': bool/None,
                        'gratuity_applicable': bool/None,
                    },
                    'salary_structure_components': {
                        'earnings': [...],
                        'deductions': [...],
                    },
                    'calculated_breakdown': {
                        'earnings': [...],
                        'deductions': [...],
                        'total_earnings': Decimal,
                        'total_deductions': Decimal,
                        'net_pay': Decimal,
                    },
                },
                ...
            ],
            'total_employees': int,
            'employees_with_config': int,
            'employees_without_config': int,
        }
    """
    try:
        # Validate admin
        admin = BaseUserModel.objects.get(id=admin_id, role='admin')
        
        # Get organization from admin
        try:
            admin_profile = AdminProfile.objects.select_related('organization').get(user=admin)
            organization = admin_profile.organization
        except AdminProfile.DoesNotExist:
            return {
                'error': 'Organization not found for admin',
                'employees': [],
                'total_employees': 0,
                'employees_with_config': 0,
                'employees_without_config': 0,
            }
        
        # Get employees under this admin using utility
        from utils.Employee.assignment_utils import get_employee_ids_under_admin
        employee_ids = get_employee_ids_under_admin(admin_id, active_only=True)
        
        employees_query = BaseUserModel.objects.filter(
            role='user',
            id__in=employee_ids
        )
        
        # If employee parameter is provided, filter to only that employee
        if employee_id:
            employees_query = employees_query.filter(id=employee_id)
        
        employees = employees_query.select_related('own_user_profile').prefetch_related(
            'own_user_profile__shifts'
        ).distinct()
        
        # Get payroll settings for organization (once for all employees)
        try:
            payroll_settings = OrganizationPayrollSettings.objects.get(organization=organization)
        except OrganizationPayrollSettings.DoesNotExist:
            payroll_settings = None
        
        # Get PT rules cache (state-wise) - store actual rule objects, not dicts
        pt_rules_cache = {}
        if payroll_settings and payroll_settings.pt_enabled:
            pt_rules = ProfessionalTaxRule.objects.filter(is_active=True)
            for rule in pt_rules:
                # Use state_name directly from model
                state_name = getattr(rule, 'state_name', None)
                if not state_name and hasattr(rule, 'state') and rule.state:
                    state_name = getattr(rule.state, 'name', None)
                
                if state_name:
                    if state_name not in pt_rules_cache:
                        pt_rules_cache[state_name] = []
                    # Store actual rule object (not dict) to match calculate_pt function expectations
                    pt_rules_cache[state_name].append(rule)
        
        # Get all employee payroll configs for the month/year (batch fetch)
        employee_configs = EmployeePayrollConfig.objects.filter(
            admin=admin,
            effective_month=month,
            effective_year=year,
            is_active=True
        ).select_related(
            'employee',
            'salary_structure',
            'employee__own_user_profile'
        )
        
        # Create a map: employee_id -> config
        config_map = {str(config.employee.id): config for config in employee_configs}
        
        # Get all structure IDs for batch fetching structure items
        structure_ids = [config.salary_structure_id for config in employee_configs]
        structure_items_map = {}
        if structure_ids:
            structure_items = SalaryStructureItem.objects.filter(
                structure_id__in=structure_ids
            ).select_related('component', 'calculation_base').order_by('order', 'id')
            
            for item in structure_items:
                structure_id = item.structure_id
                if structure_id not in structure_items_map:
                    structure_items_map[structure_id] = []
                structure_items_map[structure_id].append(item)
        
        # Build employee details list
        employee_details_list = []
        employees_with_config = 0
        employees_without_config = 0
        
        for employee in employees:
            try:
                user_profile = employee.own_user_profile
            except UserProfile.DoesNotExist:
                continue
            
            employee_id = str(employee.id)
            config = config_map.get(employee_id)
            
            # Get assigned shifts
            assigned_shifts = []
            for shift in user_profile.shifts.filter(is_active=True):
                assigned_shifts.append({
                    'shift_id': shift.id,
                    'shift_name': shift.shift_name,
                    'start_time': str(shift.start_time),
                    'end_time': str(shift.end_time),
                    'duration_minutes': shift.duration_minutes,
                    'is_night_shift': shift.is_night_shift,
                })
            
            employee_data = {
                'employee_id': employee_id,
                'employee_name': user_profile.user_name or employee.username or 'N/A',
                'custom_employee_id': user_profile.custom_employee_id or 'N/A',
                'designation': user_profile.designation or 'N/A',
                'state': user_profile.state or 'N/A',
                'city': user_profile.city or 'N/A',
                'assigned_shifts': assigned_shifts,
                'payroll_config': None,
                'salary_structure_components': {
                    'earnings': [],
                    'deductions': [],
                },
                'calculated_breakdown': None,
            }
            
            if config:
                employees_with_config += 1
                
                # Payroll config details
                structure = config.salary_structure
                structure_items = structure_items_map.get(structure.id, [])
                
                # Calculate monthly gross salary (gross_salary is stored as annual in DB)
                gross_salary_monthly = config.gross_salary / Decimal('12') if config.gross_salary else Decimal('0.00')
                employee_data['payroll_config'] = {
                    'config_id': config.id,
                    'gross_salary': str(config.gross_salary),  # Annual gross (as stored in DB)
                    'gross_salary_annual': str(config.gross_salary),  # Annual gross
                    'gross_salary_monthly': str(round(gross_salary_monthly, 2)),  # Monthly gross
                    'effective_month': config.effective_month,
                    'effective_year': config.effective_year,
                    'salary_structure_id': structure.id,
                    'salary_structure_name': structure.name,
                    'pf_applicable': config.pf_applicable,
                    'esi_applicable': config.esi_applicable,
                    'pt_applicable': config.pt_applicable,
                    'gratuity_applicable': config.gratuity_applicable,
                }
                
                # Salary structure components
                earnings_components = []
                deductions_components = []
                
                for item in structure_items:
                    component = item.component
                    component_data = {
                        'component_id': component.id,
                        'component_code': component.code,
                        'component_name': component.name,
                        'component_type': component.component_type,
                        'calculation_type': item.calculation_type,
                        'value': str(item.value) if item.value else '0.00',
                        'order': item.order,
                        'is_statutory': bool(component.statutory_type),
                        'statutory_type': component.statutory_type,
                    }
                    
                    if item.calculation_base:
                        component_data['calculation_base'] = {
                            'code': item.calculation_base.code,
                            'name': item.calculation_base.name,
                        }
                    
                    if component.component_type == 'earning':
                        earnings_components.append(component_data)
                    else:
                        deductions_components.append(component_data)
                
                employee_data['salary_structure_components'] = {
                    'earnings': earnings_components,
                    'deductions': deductions_components,
                }
                
                # Calculate breakdown
                employee_state = user_profile.state
                breakdown = calculate_payroll_breakdown_optimized(
                    config,
                    structure_items,
                    payroll_settings,
                    employee_state,
                    pt_rules_cache
                )
                
                employee_data['calculated_breakdown'] = {
                    'earnings': [
                        {
                            'component': item['component'],
                            'amount': str(item['amount']),
                        }
                        for item in breakdown['earnings']
                    ],
                    'deductions': [
                        {
                            'component': item['component'],
                            'amount': str(item['amount']),
                        }
                        for item in breakdown['deductions']
                    ],
                    'total_earnings': str(breakdown['total_earnings']),
                    'total_deductions': str(breakdown['total_deductions']),
                    'net_pay': str(breakdown['net_pay']),
                }
            else:
                employees_without_config += 1
            
            employee_details_list.append(employee_data)
        
        return {
            'employees': employee_details_list,
            'total_employees': len(employee_details_list),
            'employees_with_config': employees_with_config,
            'employees_without_config': employees_without_config,
            'month': month,
            'year': year,
            'admin_id': str(admin_id),
        }
        
    except BaseUserModel.DoesNotExist:
        return {
            'error': 'Admin not found',
            'employees': [],
            'total_employees': 0,
            'employees_with_config': 0,
            'employees_without_config': 0,
        }
    except Exception as e:
        return {
            'error': str(e),
            'employees': [],
            'total_employees': 0,
            'employees_with_config': 0,
            'employees_without_config': 0,
        }
