"""
Additional Utility APIs for Attendance/WorkLog
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, date, timedelta

from .models import Attendance
from AuthN.models import BaseUserModel, UserProfile, AdminProfile
from SiteManagement.models import Site
from .serializers import AttendanceSerializer
from AuthN.serializers import UserProfileReadSerializer
from utils.pagination_utils import CustomPagination
from utils.site_filter_utils import filter_queryset_by_site


class AttendanceDashboardAPIView(APIView):
    """Attendance Dashboard Statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, org_id):
        try:
            organization = get_object_or_404(BaseUserModel, id=org_id, role='organization')
            
            today = date.today()
            
            # Today's Statistics
            today_attendance = Attendance.objects.filter(
                user__own_user_profile__organization=organization,
                attendance_date=today
            )
            
            present = today_attendance.filter(check_in_time__isnull=False).count()
            absent = UserProfile.objects.filter(
                organization=organization,
                user__is_active=True
            ).count() - present
            
            # This Month Statistics
            month_start = date(today.year, today.month, 1)
            month_attendance = Attendance.objects.filter(
                user__own_user_profile__organization=organization,
                attendance_date__gte=month_start,
                attendance_date__lte=today
            )
            
            total_working_hours = month_attendance.aggregate(
                total=Sum('total_working_minutes')
            )['total'] or 0
            total_working_hours = total_working_hours / 60  # Convert to hours
            
            avg_working_hours = month_attendance.aggregate(
                avg=Avg('total_working_minutes')
            )['avg'] or 0
            avg_working_hours = avg_working_hours / 60
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Attendance dashboard data fetched successfully",
                "data": {
                    "today": {
                        "present": present,
                        "absent": absent,
                        "attendance_rate": round((present / (present + absent) * 100) if (present + absent) > 0 else 0, 2)
                    },
                    "this_month": {
                        "total_working_hours": round(total_working_hours, 2),
                        "average_working_hours": round(avg_working_hours, 2),
                        "total_records": month_attendance.count()
                    }
                }
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeAttendanceHistoryAPIView(APIView):
    """Get employee attendance history"""
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request, org_id, employee_id):
        try:
            organization = get_object_or_404(BaseUserModel, id=org_id, role='organization')
            employee = get_object_or_404(BaseUserModel, id=employee_id, role='user')
            
            attendances = Attendance.objects.filter(
                user=employee
            ).order_by('-attendance_date')
            
            # Filters
            from_date = request.query_params.get('from_date')
            to_date = request.query_params.get('to_date')
            status_filter = request.query_params.get('status')  # present, absent
            
            if from_date:
                attendances = attendances.filter(attendance_date__gte=from_date)
            if to_date:
                attendances = attendances.filter(attendance_date__lte=to_date)
            if status_filter == 'present':
                attendances = attendances.filter(check_in_time__isnull=False)
            elif status_filter == 'absent':
                attendances = attendances.filter(check_in_time__isnull=True)
            
            paginator = self.pagination_class()
            paginated_qs = paginator.paginate_queryset(attendances, request)
            
            # Serialize manually
            data = []
            for att in paginated_qs:
                data.append({
                    "id": str(att.id),
                    "attendance_date": att.attendance_date.isoformat(),
                    "check_in_time": att.check_in_time.isoformat() if att.check_in_time else None,
                    "check_out_time": att.check_out_time.isoformat() if att.check_out_time else None,
                    "total_working_minutes": att.total_working_minutes,
                    "status": "present" if att.check_in_time else "absent"
                })
            
            pagination_data = paginator.get_paginated_response(data)
            
            # Summary
            total_days = attendances.count()
            present_days = attendances.filter(check_in_time__isnull=False).count()
            total_hours = sum([a.total_working_minutes or 0 for a in attendances]) / 60
            
            pagination_data["summary"] = {
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": total_days - present_days,
                "total_hours": round(total_hours, 2),
                "attendance_rate": round((present_days / total_days * 100) if total_days > 0 else 0, 2)
            }
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Attendance history fetched successfully",
                "data": pagination_data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeDailyInfoAPIView(APIView):
    """
    Get Employee Daily Information API
    Returns employee profile and attendance info for today
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, site_id):
        """
        Get employee daily info under an admin
        
        Query Params:
            date (optional): Date in YYYY-MM-DD format (default: today)
            employee_id (optional): Specific employee UUID
            status (optional): Filter by present/absent
            admin_id (optional): Admin UUID (required for organization role)
            
        Returns:
            List of employees with their daily attendance info
        """
        try:
            # Get admin_id based on role
            if request.user.role == 'admin':
                admin_id = request.user.id
                admin = request.user
            elif request.user.role == 'organization':
                # Organization role: get admin_id from query params
                admin_id = request.query_params.get('admin_id')
                if not admin_id:
                    return Response({
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "admin_id is required for organization role. Please provide admin_id as query parameter.",
                        "data": []
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate admin exists and belongs to organization
                try:
                    admin = BaseUserModel.objects.get(id=admin_id, role='admin')
                    # Verify admin belongs to organization
                    admin_profile = AdminProfile.objects.filter(
                        user=admin,
                        organization=request.user
                    ).first()
                    if not admin_profile:
                        return Response({
                            "status": status.HTTP_403_FORBIDDEN,
                            "message": "Admin does not belong to your organization",
                            "data": []
                        }, status=status.HTTP_403_FORBIDDEN)
                except BaseUserModel.DoesNotExist:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Admin not found",
                        "data": []
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
                    "data": []
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate site belongs to admin
            try:
                site = Site.objects.get(id=site_id, created_by_admin=admin, is_active=True)
            except Site.DoesNotExist:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Site not found or you don't have permission to access this site",
                    "data": []
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get date from query params (default: today)
            date_str = request.query_params.get('date')
            if date_str:
                try:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response({
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "Invalid date format. Use YYYY-MM-DD"
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                target_date = date.today()
            
            # Get employee filter
            employee_id = request.query_params.get('employee_id')
            status_filter = request.query_params.get('status')  # present/absent
            
            # Get all employees under admin and site
            employees_queryset = UserProfile.objects.filter(
                admin=admin,
                site=site,
                user__is_active=True
            ).select_related('user')
            
            # Filter by specific employee
            if employee_id:
                employees_queryset = employees_queryset.filter(user_id=employee_id)
            
            employees_data = []
            
            for profile in employees_queryset:
                # Get attendance for the target date
                try:
                    attendance = Attendance.objects.get(
                        user=profile.user,
                        attendance_date=target_date
                    )
                    attendance_data = {
                        "id": str(attendance.id),
                        "check_in_time": attendance.check_in_time.strftime('%H:%M:%S') if attendance.check_in_time else None,
                        "check_out_time": attendance.check_out_time.strftime('%H:%M:%S') if attendance.check_out_time else None,
                        "working_hours": float(attendance.working_hours) if attendance.working_hours else 0.0,
                        "status": "present",
                        "check_in_location": attendance.check_in_location,
                        "check_out_location": attendance.check_out_location,
                        "check_in_image": attendance.check_in_image.url if attendance.check_in_image else None,
                    }
                    is_present = True
                except Attendance.DoesNotExist:
                    attendance_data = {
                        "id": None,
                        "check_in_time": None,
                        "check_out_time": None,
                        "working_hours": 0.0,
                        "status": "absent",
                        "check_in_location": None,
                        "check_out_location": None,
                        "check_in_image": None,
                    }
                    is_present = False
                
                # Apply status filter
                if status_filter:
                    if status_filter == 'present' and not is_present:
                        continue
                    elif status_filter == 'absent' and is_present:
                        continue
                
                # Build employee data
                employee_info = {
                    "employee_id": str(profile.user.id),
                    "user_name": profile.user_name,
                    "email": profile.user.email,
                    "custom_employee_id": profile.custom_employee_id,
                    "designation": profile.designation,
                    "job_title": profile.job_title,
                    "profile_photo": profile.profile_photo.url if profile.profile_photo else None,
                    "phone_number": profile.user.phone_number,
                    "date": target_date.strftime('%Y-%m-%d'),
                    "attendance": attendance_data
                }
                
                employees_data.append(employee_info)
            
            # Summary
            total_employees = len(employees_queryset)
            present_count = sum(1 for emp in employees_data if emp['attendance']['status'] == 'present')
            absent_count = total_employees - present_count
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Employee daily info fetched successfully",
                "date": target_date.strftime('%Y-%m-%d'),
                "summary": {
                    "total_employees": total_employees,
                    "present": present_count,
                    "absent": absent_count
                },
                "data": employees_data
            })
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

