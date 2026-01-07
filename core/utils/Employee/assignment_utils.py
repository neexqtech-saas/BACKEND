"""
Employee Assignment Utility Functions
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from datetime import date

from AuthN.models import BaseUserModel, UserProfile
from SiteManagement.models import EmployeeAdminSiteAssignment


def get_current_admin_for_employee(employee):
    """
    Get current active admin for an employee from assignments - O(1) query.
    
    Args:
        employee: BaseUserModel instance with role='user'
    
    Returns:
        BaseUserModel (admin) or None if no active assignment found
    """
    if not employee or employee.role != 'user':
        return None
    
    # O(1) query using index assignment_emp_active_idx
    assignment = EmployeeAdminSiteAssignment.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('admin', 'admin__own_admin_profile').only(
        'id', 'admin_id', 'admin__id', 'admin__role', 'admin__email'
    ).order_by('-start_date').first()
    
    return assignment.admin if assignment else None


def get_current_assignment_for_employee(employee):
    """
    Get current active assignment for an employee - O(1) query.
    
    Args:
        employee: BaseUserModel instance with role='user'
    
    Returns:
        EmployeeAdminSiteAssignment or None
    """
    if not employee or employee.role != 'user':
        return None
    
    # O(1) query using index assignment_emp_active_idx
    return EmployeeAdminSiteAssignment.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('admin', 'admin__own_admin_profile', 'site').only(
        'id', 'employee_id', 'admin_id', 'site_id', 'start_date', 
        'end_date', 'is_active'
    ).order_by('-start_date').first()


def verify_employee_under_admin(employee, admin, raise_exception=True):
    """
    Verify if employee is currently assigned under the given admin - O(1) query.
    
    Args:
        employee: BaseUserModel instance with role='user'
        admin: BaseUserModel instance with role='admin'
        raise_exception: If True, raises ValidationError; if False, returns boolean
    
    Returns:
        bool: True if employee is under admin, False otherwise
        or raises ValidationError if raise_exception=True and not found
    """
    if not employee or employee.role != 'user':
        if raise_exception:
            raise ValidationError("Invalid employee")
        return False
    
    if not admin or admin.role != 'admin':
        if raise_exception:
            raise ValidationError("Invalid admin")
        return False
    
    # O(1) query using index assignment_emp_admin_idx
    assignment = EmployeeAdminSiteAssignment.objects.filter(
        employee=employee,
        admin=admin,
        is_active=True
    ).only('id').first()
    
    if assignment:
        return True
    
    if raise_exception:
        raise ValidationError("Employee is not under this admin")
    
    return False


def get_employees_under_admin(admin, active_only=True):
    """
    Get all employees currently assigned under an admin - O(1) query.
    
    Args:
        admin: BaseUserModel instance with role='admin'
        active_only: If True, only return employees with active assignments
    
    Returns:
        QuerySet of employee IDs (UUIDs)
    """
    if not admin or admin.role != 'admin':
        return BaseUserModel.objects.none()
    
    filter_kwargs = {'admin': admin}
    if active_only:
        filter_kwargs['is_active'] = True
    
    # O(1) query using index assignment_admin_active_idx
    assignments = EmployeeAdminSiteAssignment.objects.filter(**filter_kwargs).only('employee_id')
    employee_ids = assignments.values_list('employee_id', flat=True).distinct()
    
    return employee_ids


def get_employee_ids_under_admin(admin_id, active_only=True, site_id=None):
    """
    Get all employee IDs currently assigned under an admin (by admin_id) - O(1) query.
    
    Args:
        admin_id: UUID string or UUID object of admin
        active_only: If True, only return employees with active assignments
        site_id: Optional UUID of site to filter by
    
    Returns:
        QuerySet of employee IDs (UUIDs)
    """
    try:
        # O(1) query - Validate admin
        admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
        employee_ids = get_employees_under_admin(admin, active_only=active_only)
        
        # Filter by site if provided - O(1) query using index assignment_site_dates_idx
        if site_id:
            # Use common function to get employees assigned to site
            site_employee_ids = get_employees_assigned_to_site(admin_id, site_id, check_date=None, active_only=active_only)
            employee_ids = employee_ids.filter(id__in=site_employee_ids)
        
        return employee_ids
    except BaseUserModel.DoesNotExist:
        return BaseUserModel.objects.none()


def get_user_profiles_under_admin(admin_id, active_only=True, site_id=None):
    """
    Get UserProfile queryset for employees under an admin - O(1) query.
    
    Args:
        admin_id: UUID string or UUID object of admin
        active_only: If True, only return employees with active assignments
        site_id: Optional UUID of site to filter by
    
    Returns:
        QuerySet of UserProfile objects
    """
    employee_ids = get_employee_ids_under_admin(admin_id, active_only=active_only, site_id=site_id)
    # O(1) query with select_related to avoid N+1
    return UserProfile.objects.filter(user_id__in=employee_ids).select_related('user', 'organization').only(
        'id', 'user_id', 'organization_id', 'user_name', 'custom_employee_id', 
        'designation', 'job_title', 'gender', 'date_of_joining', 'state', 
        'city', 'user__email', 'user__is_active'
    )


def verify_and_get_employee_profile(employee_id, admin_id, raise_response=True):
    """
    Verify employee is under admin and return profile - O(1) queries.
    Helper for views that need to verify employee-admin relationship.
    
    Args:
        employee_id: UUID string or UUID object of employee
        admin_id: UUID string or UUID object of admin
        raise_response: If True, returns Response with error; if False, raises exception
    
    Returns:
        tuple: (employee, admin, profile) or (None, None, None) if not found
        or Response object if raise_response=True and verification fails
    """
    try:
        # O(1) queries - Validate employee and admin
        employee = BaseUserModel.objects.only('id', 'role').get(id=employee_id, role='user')
        admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
        
        # Verify employee is under admin - O(1) query
        if not verify_employee_under_admin(employee, admin, raise_exception=False):
            if raise_response:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Employee is not under this admin",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            return None, None, None
        
        # O(1) query - Get profile with select_related
        profile = UserProfile.objects.select_related('user', 'organization').filter(
            user=employee
        ).only('id', 'user_id', 'organization_id', 'user_name').first()
        
        if not profile:
            if raise_response:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Employee profile not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            return None, None, None
        
        return employee, admin, profile
        
    except BaseUserModel.DoesNotExist:
        if raise_response:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Employee or admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        return None, None, None
    except UserProfile.DoesNotExist:
        if raise_response:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Employee profile not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        return None, None, None


def get_employees_assigned_to_site(admin_id, site_id, check_date=None, active_only=True):
    """
    Get all employee IDs assigned to a site on a specific date (or today) - O(1) query.
    This is a common pattern used across multiple APIs.
    
    Args:
        admin_id: UUID string or UUID object of admin
        site_id: UUID string or UUID object of site
        check_date: Date to check assignment (default: today). If None, uses today
        active_only: If True, only return employees with active assignments
    
    Returns:
        QuerySet of employee IDs (UUIDs)
    """
    if check_date is None:
        check_date = date.today()
    
    filter_kwargs = {
        'site_id': site_id,
        'admin_id': admin_id,
        'start_date__lte': check_date
    }
    
    if active_only:
        filter_kwargs['is_active'] = True
    
    # O(1) query using index assignment_site_dates_idx
    assignments = EmployeeAdminSiteAssignment.objects.filter(**filter_kwargs).filter(
        Q(end_date__gte=check_date) | Q(end_date__isnull=True)
    ).only('employee_id')
    
    return assignments.values_list('employee_id', flat=True).distinct()


def is_employee_assigned_to_site(employee_id, admin_id, site_id, check_date=None):
    """
    Check if employee is assigned to site on specific date - O(1) query.
    Common validation used across multiple APIs.
    
    Args:
        employee_id: UUID string or UUID object of employee
        admin_id: UUID string or UUID object of admin
        site_id: UUID string or UUID object of site
        check_date: Date to check (default: today). If None, uses today
    
    Returns:
        bool: True if assigned, False otherwise
    """
    if check_date is None:
        check_date = date.today()
    
    # O(1) query using index assignment_site_dates_idx
    return EmployeeAdminSiteAssignment.objects.filter(
        employee_id=employee_id,
        site_id=site_id,
        admin_id=admin_id,
        is_active=True,
        start_date__lte=check_date
    ).filter(
        Q(end_date__gte=check_date) | Q(end_date__isnull=True)
    ).only('id').exists()


def get_active_assignments_for_employee(employee_id, admin_id=None, site_id=None):
    """
    Get all active assignments for an employee - O(1) query.
    Can optionally filter by admin and/or site.
    
    Args:
        employee_id: UUID string or UUID object of employee
        admin_id: Optional UUID of admin to filter by
        site_id: Optional UUID of site to filter by
    
    Returns:
        QuerySet of EmployeeAdminSiteAssignment objects
    """
    filter_kwargs = {
        'employee_id': employee_id,
        'is_active': True
    }
    
    if admin_id:
        filter_kwargs['admin_id'] = admin_id
    
    if site_id:
        filter_kwargs['site_id'] = site_id
    
    # O(1) query using index assignment_emp_active_idx or assignment_emp_admin_idx
    return EmployeeAdminSiteAssignment.objects.filter(**filter_kwargs).select_related(
        'employee', 'employee__own_user_profile',
        'admin', 'admin__own_admin_profile', 
        'site', 'assigned_by'
    ).only(
        'id', 'employee_id', 'admin_id', 'site_id', 'assigned_by_id',
        'start_date', 'end_date', 'is_active', 'assignment_reason'
    ).order_by('-start_date')


def get_assignments_by_date_range(admin_id, site_id=None, start_date=None, end_date=None, active_only=True):
    """
    Get assignments active within a date range - O(1) query.
    Useful for reports and filtering by date ranges.
    
    Args:
        admin_id: UUID string or UUID object of admin
        site_id: Optional UUID of site to filter by
        start_date: Start of date range (default: None, no lower limit)
        end_date: End of date range (default: None, no upper limit)
        active_only: If True, only return active assignments
    
    Returns:
        QuerySet of EmployeeAdminSiteAssignment objects
    """
    filter_kwargs = {
        'admin_id': admin_id
    }
    
    if site_id:
        filter_kwargs['site_id'] = site_id
    
    if active_only:
        filter_kwargs['is_active'] = True
    
    # O(1) query using index assignment_admin_active_idx or assignment_site_dates_idx
    assignments = EmployeeAdminSiteAssignment.objects.filter(**filter_kwargs)
    
    # Apply date range filtering
    if start_date and end_date:
        # Assignment is active if it overlaps with the date range
        assignments = assignments.filter(
            Q(start_date__lte=end_date) & (
                Q(end_date__gte=start_date) | Q(end_date__isnull=True)
            )
        )
    elif start_date:
        # Only check if assignment starts before or on end_date
        assignments = assignments.filter(
            Q(end_date__gte=start_date) | Q(end_date__isnull=True)
        )
    elif end_date:
        # Only check if assignment starts before or on end_date
        assignments = assignments.filter(start_date__lte=end_date)
    
    return assignments.select_related(
        'employee', 'employee__own_user_profile',
        'admin', 'admin__own_admin_profile', 
        'site', 'assigned_by'
    ).only(
        'id', 'employee_id', 'admin_id', 'site_id', 'assigned_by_id',
        'start_date', 'end_date', 'is_active', 'assignment_reason'
    ).order_by('-start_date')


def get_employee_ids_for_site_on_date(admin_id, site_id, check_date=None):
    """
    Get list of employee IDs assigned to a site on a specific date - O(1) query.
    Optimized version that returns a list instead of QuerySet.
    
    Args:
        admin_id: UUID string or UUID object of admin
        site_id: UUID string or UUID object of site
        check_date: Date to check (default: today)
    
    Returns:
        list: List of employee IDs (UUIDs)
    """
    employee_ids = get_employees_assigned_to_site(admin_id, site_id, check_date, active_only=True)
    return list(employee_ids)
