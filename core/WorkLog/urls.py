"""
WorkLog URL Configuration
=========================
This module defines all URL patterns for the WorkLog application,
including attendance check-in/out, employee attendance tracking,
and attendance analytics endpoints.
"""

from django.urls import path
from .views import *
from .additional_utility_views import *


urlpatterns = [
    # ==================== Attendance Check-In/Check-Out ====================
    
    # POST: Check-in or Check-out for an employee
    # - If no open attendance exists: Creates new check-in record
    # - If open attendance exists: Updates with check-out time
    path(
        'attendance-check/<uuid:userid>',
        AttendanceCheckInOutAPIView.as_view(),
        name='attendance-checks'
    ),
    
    
    # ==================== Employee Attendance Fetching ====================
    
    # GET: Fetch attendance for a specific employee under an admin and site
    # URL params: site_id (UUID, required), user_id (UUID)
    # Query params: date (required), status (optional), export (optional), page, page_size, admin_id (for organization role)
    path(
        'employee-attendance/<uuid:site_id>/<uuid:user_id>/',
        FetchEmployeeAttendanceAPIView.as_view(),
        name='fetch-employee-attendance-by-user-with-site'
    ),
    
    # GET: Fetch attendance for all employees under an admin and site
    # URL params: site_id (UUID, required)
    # Query params: date (required), status (optional), export (optional), page, page_size, admin_id (for organization role)
    path(
        'employee-attendance/<uuid:site_id>/',
        FetchEmployeeAttendanceAPIView.as_view(),
        name='fetch-employee-attendance-with-site'
    ),
    
    # GET: Fetch monthly present/absent count for a specific employee
    # Returns: present_days and absent_days count for the given month and year
    path(
        'employee-monthly-attendance/<uuid:site_id>/<uuid:user_id>/<int:month>/<int:year>/',
        FetchEmployeeMonthlyAttendanceAPIView.as_view(),
        name='fetch-employee-monthly-present-absent'
    ),
    
    
    # ==================== Attendance Editing ====================
    
    # PUT: Edit attendance check-in & check-out details
    # Allows updating check-in time, check-out time, and related fields
    path(
        'edit-attendance/<uuid:userid>/<int:attendance_id>',
        EditAttendanceAPIView.as_view(),
        name='edit-attendance'
    ),
    
    
    # ==================== Attendance Analytics & Utilities ====================
    
    # GET: Fetch attendance dashboard data for an organization
    # Returns aggregated attendance statistics and insights
    path(
        'dashboard/<str:org_id>',
        AttendanceDashboardAPIView.as_view(),
        name='attendance-dashboard'
    ),
    
    # GET: Fetch attendance history for a specific employee
    # Returns historical attendance records for the employee
    path(
        'employee-history/<str:org_id>/<str:employee_id>',
        EmployeeAttendanceHistoryAPIView.as_view(),
        name='employee-attendance-history'
    ),
    
    # ==================== Employee Daily Info ====================
    
    # GET: Employee daily info (profile + attendance)
    # Query params: date (optional), employee_id (optional), status (optional), admin_id (for organization role)
    path(
        'employee-daily-info/<uuid:site_id>/',
        EmployeeDailyInfoAPIView.as_view(),
        name='employee-daily-info'
    ),

]
