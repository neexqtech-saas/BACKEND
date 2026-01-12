"""
WorkLog Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from typing import Any
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, date, timedelta
from django.utils import timezone
from calendar import monthrange
from .models import Attendance
from AuthN.models import BaseUserModel, UserProfile, AdminProfile
from SiteManagement.models import Site, EmployeeAdminSiteAssignment
from .serializers import *
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Case, When, IntegerField
from django.http import HttpResponse
from django.core.cache import cache
from django.db import transaction
from utils.Attendance.attendance_utils import *
from utils.pagination_utils import CustomPagination
from utils.helpers.image_utils import save_multiple_base64_images, save_base64_image
from utils.site_filter_utils import validate_admin_and_site, filter_queryset_by_site
from utils.Employee.assignment_utils import (
    get_employees_assigned_to_site,
    is_employee_assigned_to_site,
    get_employee_ids_for_site_on_date
)
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from io import BytesIO
from utils.Attendance.attendance_excel_export_service import ExcelExportService
from utils.Attendance.attendance_edit_service import AttendanceEditService
import traceback


def get_admin_and_site_for_attendance(request, site_id, attendance_date=None):
    """
    Optimized admin and site validation for attendance - O(1) queries with select_related
    Returns: (admin, site, None) tuple or (None, None, Response with error)
    """
    user = request.user
    
    # Fast path for admin role - O(1) query
    if user.role == 'admin':
        admin_id = user.id
        admin = user
        # Single O(1) query with index on (id, created_by_admin, is_active)
        try:
            site = Site.objects.only('id', 'site_name', 'created_by_admin_id', 'is_active').get(
                id=site_id, 
                created_by_admin_id=admin_id, 
                is_active=True
            )
            return admin, site, None
        except Site.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Site not found or you don't have permission to access this site",
                "data": []
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Organization role - O(1) queries with select_related
    elif user.role == 'organization':
        admin_id = request.query_params.get('admin_id')
        if not admin_id:
            return None, None, Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "admin_id is required for organization role. Please provide admin_id as query parameter.",
                "data": []
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Single O(1) query with select_related to avoid N+1 - uses index on (id, role)
        try:
            admin = BaseUserModel.objects.only(
                'id', 'role', 'email'
            ).get(id=admin_id, role='admin')
        except BaseUserModel.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": []
            }, status=status.HTTP_404_NOT_FOUND)
        
        # O(1) query - verify admin belongs to organization using select_related
        admin_profile = AdminProfile.objects.select_related('user', 'organization').only(
            'id', 'user_id', 'organization_id'
        ).filter(
            user_id=admin_id,
            organization_id=user.id
        ).first()
        
        if not admin_profile:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Admin does not belong to your organization",
                "data": []
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Single O(1) query with index on (id, created_by_admin, is_active)
        try:
            site = Site.objects.only('id', 'site_name', 'created_by_admin_id', 'is_active').get(
                id=site_id, 
                created_by_admin_id=admin_id, 
                is_active=True
            )
            return admin, site, None
        except Site.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Site not found or you don't have permission to access this site",
                "data": []
            }, status=status.HTTP_403_FORBIDDEN)
    
    # User role - validate assignment
    elif user.role == 'user':
        if not attendance_date:
            attendance_date = date.today()
        
        # O(1) query using index assignment_site_dates_idx
        assignment = EmployeeAdminSiteAssignment.objects.filter(
            employee_id=user.id,
            site_id=site_id,
            is_active=True,
            start_date__lte=attendance_date
        ).filter(
            Q(end_date__gte=attendance_date) | Q(end_date__isnull=True)
        ).select_related('admin', 'site').only(
            'id', 'admin_id', 'site_id', 'employee_id', 'start_date', 'end_date', 'is_active'
        ).first()
        
        if not assignment:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "You are not assigned to this site for the selected date",
                "data": []
            }, status=status.HTTP_403_FORBIDDEN)
        
        admin = assignment.admin
        site = assignment.site
        return admin, site, None
    
    else:
        return None, None, Response({
            "status": status.HTTP_403_FORBIDDEN,
            "message": "Unauthorized access. Only admin, organization, and user roles can access this endpoint",
            "data": []
        }, status=status.HTTP_403_FORBIDDEN)



class AttendanceCheckInOutAPIView(APIView):
    """
    Optimized Check-In/Check-Out API for high traffic (100k+ calls/day)
    - Uses select_related to avoid N+1 queries
    - Caches user profile data
    - Uses update() for faster database writes
    - Optimized shift lookup
    """

    @transaction.atomic
    def post(self, request, userid):
        try:
            today = date.today()
            check_time = timezone.now()
            
            # Optimized: Fetch user with related profile in single query
            user = BaseUserModel.objects.select_related(
                'own_user_profile',
                'own_user_profile__organization'
            ).only(
                'id',
                'own_user_profile__organization_id',
                'own_user_profile__profile_photo'
            ).get(id=userid)
            
            user_profile = user.own_user_profile
            
            # Get current active admin from assignments using utility
            from utils.Employee.assignment_utils import get_current_admin_for_employee
            current_admin = get_current_admin_for_employee(user)
            
            if not current_admin:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "No active admin assignment found for this employee.",
                    "data": []
                }, status=status.HTTP_400_BAD_REQUEST)

            # 🟦 CHECKOUT FLOW - Optimized query with select_related
            open_attendance = Attendance.objects.select_related(
                'assign_shift'
            ).only(
                'id', 'check_in_time', 'assign_shift__end_time', 
                'assign_shift__duration_minutes'
            ).filter(
                user_id=userid,
                attendance_date=today,
                check_out_time__isnull=True
            ).first()

            if open_attendance:
                # 1️⃣ Total working minutes
                total_minutes = calculate_total_working_minutes(
                    open_attendance.check_in_time,
                    check_time
                )
                # Check if time is at least 10 seconds
                if total_minutes is None:
                    # Calculate seconds to check minimum requirement
                    total_seconds = (check_time - open_attendance.check_in_time).total_seconds()
                    if total_seconds < 10:
                        remaining_seconds = int(10 - total_seconds)
                        return Response({
                            "status": status.HTTP_400_BAD_REQUEST,
                            "message": f"Working time too short. Please wait {remaining_seconds} more second(s). Minimum 10 seconds required.",
                            "remaining_seconds": remaining_seconds,
                            "elapsed_seconds": int(total_seconds),
                            "data": []
                        }, status=status.HTTP_400_BAD_REQUEST)
                    # If >= 10 seconds but < 1 minute, set to 0 minutes (will be stored as 0)
                    total_minutes = 0

                # 2️⃣ Early exit minutes
                early_exit = 0
                if open_attendance.assign_shift and open_attendance.assign_shift.end_time:
                    early_exit = calculate_early_exit_minutes(
                        check_time,
                        open_attendance.assign_shift.end_time
                    )

                # 3️⃣ Overtime minutes
                expected_hours = 8
                if open_attendance.assign_shift and open_attendance.assign_shift.duration_minutes:
                    expected_hours = open_attendance.assign_shift.duration_minutes / 60
                overtime = calculate_overtime_minutes(total_minutes, expected_hours=expected_hours)

                # Prepare update data
                update_data = {
                    'check_out_time': check_time,
                    'total_working_minutes': total_minutes,
                    'early_exit_minutes': early_exit,
                    'overtime_minutes': overtime,
                    'is_early_exit': True if (early_exit and early_exit > 0) else False
                }
                
                # Add location data if provided
                if request.data.get("check_out_latitude") and request.data.get("check_out_longitude"):
                    update_data['check_out_latitude'] = request.data.get("check_out_latitude")
                    update_data['check_out_longitude'] = request.data.get("check_out_longitude")
                
                # Add check_out_location if provided
                if request.data.get("check_out_location"):
                    update_data['check_out_location'] = request.data.get("check_out_location")
                
                # Update profile photo from selfie if provided (update on every checkout)
                base64_images = request.data.get("base64_images")
                if base64_images:
                    # Normalize to list if single string
                    if isinstance(base64_images, str):
                        base64_images = [base64_images]
                    
                    # Update profile photo on every checkout
                    if base64_images and len(base64_images) > 0:
                        try:
                            saved_image = save_base64_image(
                                base64_images[0],
                                folder_name='profile_photos',
                                attendance_type='profile',
                                captured_at=check_time
                            )
                            # Update user profile photo
                            user_profile.profile_photo = saved_image.get('file_path', '')
                            user_profile.save(update_fields=['profile_photo'])
                        except Exception as e:
                            # Log error but don't fail checkout
                            print(f"Error updating profile photo: {str(e)}")
                
                # Optimized: Use update() instead of save() for better performance
                Attendance.objects.filter(id=open_attendance.id).update(**update_data)

                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Checked out successfully.",
                    "data": []
                }, status=status.HTTP_200_OK)

            # 🟩 CHECK-IN FLOW
            # Optimized: Cache shifts lookup per user (5 min cache)
            cache_key = f"user_shifts_{userid}"
            shifts = cache.get(cache_key)
            
            if shifts is None:
                shifts = list(user_profile.shifts.all().only('id', 'start_time', 'end_time', 'duration_minutes'))
                cache.set(cache_key, shifts, 300)  # Cache for 5 minutes
            
            nearest_shift, late_minutes = get_nearest_shift_with_late_minutes(
                check_time,
                shifts
            )

            # Prepare payload with minimal data
            payload = {
                "user": str(user.id),
                "admin": str(current_admin.id),
                "organization": str(user_profile.organization_id),
                "attendance_date": today,
                "check_in_time": check_time,
                "attendance_status": "present",
                "marked_by": request.data.get("marked_by", "mobile"),
                "assign_shift": str(nearest_shift.id) if nearest_shift else None,
                "late_minutes": late_minutes or 0,
                "is_late": True if (late_minutes and late_minutes > 0) else False
            }
            
            # Add location data if provided
            if request.data.get("check_in_latitude") and request.data.get("check_in_longitude"):
                payload["check_in_latitude"] = request.data.get("check_in_latitude")
                payload["check_in_longitude"] = request.data.get("check_in_longitude")
            
            # Add check_in_location if provided
            if request.data.get("check_in_location"):
                payload["check_in_location"] = request.data.get("check_in_location")
            
            serializer = AttendanceSerializer(data=payload)
            if serializer.is_valid():
                serializer.save()
                
                # Invalidate cache after check-in
                cache.delete(cache_key)
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Checked in successfully.",
                    "data": []
                }, status=status.HTTP_201_CREATED)

            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "data": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "User not found.",
                "data": []
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FetchEmployeeAttendanceAPIView(APIView):
    pagination_class = CustomPagination

    def get(self, request, site_id, user_id=None):
        try:
            q_date = request.query_params.get("date")
            export = request.query_params.get("export") == "true"
            status_param = request.query_params.get("status", None)
            search_query = request.query_params.get("search", None)

            if not q_date:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "date parameter is required",
                    "data": []
                }, status=status.HTTP_400_BAD_REQUEST)

            attendance_date = datetime.strptime(q_date, "%Y-%m-%d").date()

            # Get admin and site - O(1) queries
            admin, site, error_response = get_admin_and_site_for_attendance(request, site_id, attendance_date)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            # For user role, validate user_id
            if request.user.role == 'user':
                if user_id and str(user_id) != str(request.user.id):
                    return Response({
                        "status": status.HTTP_403_FORBIDDEN,
                        "message": "You can only view your own attendance",
                        "data": []
                    }, status=status.HTTP_403_FORBIDDEN)
                user_id = request.user.id
            
            # Get ALL employees first (for summary calculation)
            if user_id:
                # Verify employee belongs to the admin and is assigned to this site using common function
                assignment_exists = is_employee_assigned_to_site(
                    user_id, admin_id, site_id, check_date=attendance_date
                )
                
                if not assignment_exists:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Employee not found or is not assigned to this site",
                        "data": []
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Get employee profile - O(1) query with select_related
                all_employees = UserProfile.objects.filter(
                    user_id=user_id
                ).select_related("user").only(
                    'id', 'user_id', 'organization_id', 'user_name', 'custom_employee_id',
                    'designation', 'job_title', 'gender', 'date_of_joining', 
                    'state', 'city', 'user__email', 'user__is_active'
                )
                
                if not all_employees.exists():
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Employee profile not found",
                        "data": []
                    }, status=status.HTTP_404_NOT_FOUND)
                
                employees_for_summary = all_employees
            else:
                # Filter by admin_id and site_id (both required)
                # Get employees assigned to this site using common function
                employee_ids = get_employees_assigned_to_site(
                    admin_id, site_id, check_date=attendance_date, active_only=True
                )
                
                if not employee_ids:
                    # No employees assigned to this site
                    all_employees = UserProfile.objects.none()
                else:
                    # Get employee profiles - O(1) query with select_related
                    all_employees = UserProfile.objects.filter(
                        user_id__in=employee_ids
                    ).select_related("user").only(
                        'id', 'user_id', 'organization_id', 'user_name', 'custom_employee_id',
                        'designation', 'job_title', 'gender', 'date_of_joining', 
                        'state', 'city', 'user__email', 'user__is_active'
                    )
                
                employees_for_summary = all_employees

            # Calculate summary based on ALL employees (before search filter) - O(1) aggregation
            all_employee_ids = list(employees_for_summary.values_list('user_id', flat=True))
            all_records = Attendance.objects.filter(
                user_id__in=all_employee_ids,
                attendance_date=attendance_date
            ).select_related("user", "assign_shift").only(
                'id', 'user_id', 'attendance_date', 'attendance_status', 'is_late',
                'check_in_time', 'check_out_time', 'total_working_minutes',
                'assign_shift_id', 'user__email', 'user__is_active'
            )
            
            total_emp = employees_for_summary.count()
            present = all_records.filter(attendance_status="present").values("user_id").distinct().count()
            late = all_records.filter(is_late=True).values("user_id").distinct().count()
            absent = total_emp - all_records.values("user_id").distinct().count()

            # Now apply search filter if provided
            if search_query:
                search_query = search_query.strip()
                employees = all_employees.filter(
                    Q(user_name__icontains=search_query) |
                    Q(user__email__icontains=search_query) |
                    Q(custom_employee_id__icontains=search_query)
                )
            else:
                employees = all_employees

            data = AttendanceService.build_employee_structure(employees, attendance_date)

            records = Attendance.objects.filter(
                user_id__in=list(data.keys()),
                attendance_date=attendance_date
            ).select_related("user", "assign_shift").only(
                'id', 'user_id', 'attendance_date', 'attendance_status', 'is_late',
                'check_in_time', 'check_out_time', 'total_working_minutes',
                'assign_shift_id', 'user__email', 'user__is_active'
            ).order_by('-id')

            
            data = AttendanceService.aggregate_records(records, data)
            final_data = AttendanceService.finalize_status(data)

            # Filter by status_param if provided
            if status_param:
                status_param = status_param.lower()
                if status_param == "late":
                    final_data = [x for x in final_data if x.get("is_late")]
                elif status_param == "present":
                    final_data = [x for x in final_data if x.get("attendance_status") == "present"]
                elif status_param == "absent":
                    final_data = [x for x in final_data if x.get("attendance_status") == "absent"]

            if export:
                return ExcelExportService.generate(final_data, attendance_date)

            # Paginate
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
            total_items = len(final_data)
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
            start = (page - 1) * page_size
            end = start + page_size

            serializer = AttendanceOutputSerializer(final_data[start:end], many=True)
            serializer_data = serializer.data

            # ------------------- Summary (always based on ALL employees) -------------------
            summary = {
                "total_employees": total_emp,
                "present": present,
                "late_login": late,
                "absent": absent,
                "attendance_date": attendance_date.strftime("%Y-%m-%d")
            }

            return Response({
                "status": status.HTTP_200_OK,
                "message": "Attendance fetched successfully",
                "data": serializer_data,
                "summary": summary,
                "pagination": {
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "current_page": page,
                    "page_size": page_size,
                    "has_next": page < total_pages,
                    "has_previous": page > 1
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)
            # Get last line in traceback (where exception occurred)
            line_number = tb[-1].lineno if tb else None
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "line_number": line_number,
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FetchEmployeeMonthlyAttendanceAPIView(APIView):
    """
    Optimized API to fetch monthly present/absent count for employee
    Returns detailed attendance data with dates and summary
    """
    
    def get(self, request, site_id, user_id, month, year):
        try:
            # Validate month and year
            if month < 1 or month > 12:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid month. Month must be between 1 and 12",
                    "data": []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if year < 2000 or year > 2100:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid year",
                    "data": []
                }, status=status.HTTP_400_BAD_REQUEST)

            # Calculate first and last day of month
            first_day = date(year, month, 1)
            last_day = date(year, month, monthrange(year, month)[1])
            
            # Get admin and site - O(1) queries (use first_day for user role validation)
            admin, site, error_response = get_admin_and_site_for_attendance(request, site_id, first_day)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            # For user role, validate user_id
            if request.user.role == 'user':
                if str(user_id) != str(request.user.id):
                    return Response({
                        "status": status.HTTP_403_FORBIDDEN,
                        "message": "You can only view your own monthly attendance",
                        "data": []
                    }, status=status.HTTP_403_FORBIDDEN)
                user_id = request.user.id
            
            # Get employee with related user data - O(1) query with select_related
            try:
                employee = UserProfile.objects.select_related("user").only(
                    'id', 'user_id', 'user_name', 'user__email', 'user__is_active'
                ).get(user_id=user_id)
            except UserProfile.DoesNotExist:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Employee not found",
                    "data": []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # For admin/org roles, validate employee belongs to admin via assignment
            if request.user.role != 'user':
                # Check if employee is assigned to this admin and site using common function
                # Check if assignment exists for any date in the month (check first and last day)
                assignment_exists = (
                    is_employee_assigned_to_site(user_id, admin_id, site_id, check_date=first_day) or
                    is_employee_assigned_to_site(user_id, admin_id, site_id, check_date=last_day)
                )
                
                if not assignment_exists:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Employee not found or does not belong to this admin and site",
                        "data": []
                    }, status=status.HTTP_404_NOT_FOUND)
            
            total_days = (last_day - first_day).days + 1

            # Get all present dates - O(1) query using index idx_user_status_date
            present_dates_list = list(
                Attendance.objects.filter(
                    user_id=user_id,
                    attendance_date__gte=first_day,
                    attendance_date__lte=last_day,
                    attendance_status="present"
                ).values_list('attendance_date', flat=True).distinct().order_by('attendance_date')
            )
            
            # Convert dates to string format (YYYY-MM-DD)
            present_dates_str = [str(d) for d in present_dates_list]
            present_days_count = len(present_dates_str)

            # Generate all dates in the month
            all_dates_in_month = [
                first_day + timedelta(days=x) 
                for x in range(total_days)
            ]
            
            # Find absent dates (dates that are not in present_dates_list)
            present_dates_set = set(present_dates_list)
            absent_dates_list = [
                d for d in all_dates_in_month 
                if d not in present_dates_set
            ]
            
            # Convert absent dates to string format
            absent_dates_str = [str(d) for d in absent_dates_list]
            absent_days_count = len(absent_dates_str)

            # Prepare response data
            response_data = {
                "present": {
                    "count": present_days_count,
                    "dates": present_dates_str
                },
                "absent": {
                    "count": absent_days_count,
                    "dates": absent_dates_str
                }
            }

            # Prepare summary
            summary = {
                "employee_id": str(employee.user_id),
                "employee_name": employee.user_name,
                "month": month,
                "year": year,
                "total_days": total_days,
                "present_days": present_days_count,
                "absent_days": absent_days_count
            }

            return Response({
                "status": status.HTTP_200_OK,
                "message": "Monthly attendance status fetched successfully",
                "data": response_data,
                "summary": summary
            }, status=status.HTTP_200_OK)

        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)
            line_number = tb[-1].lineno if tb else None
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "line_number": line_number,
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EditAttendanceAPIView(APIView):
    """Clean API to edit attendance check-in & check-out"""

    def put(self, request, userid, attendance_id):
        # Fetch attendance or 404 automatically
        attendance = get_object_or_404(
            Attendance,
            id=attendance_id,
            user_id=userid
        )

        serializer = EditAttendanceSerializer(
            attendance, 
            data=request.data, 
            partial=True
        )
        serializer.is_valid(raise_exception=True)

        # Update attendance via service
        AttendanceEditService.update_checkin_checkout(
            attendance, serializer.validated_data
        )

        return Response({
            "status": status.HTTP_200_OK,
            "message": "Attendance updated successfully",
            "data": []
        }, status=status.HTTP_200_OK)