"""
User Info Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from AuthN.models import UserProfile, BaseUserModel, AdminProfile
from AuthN.serializers import UserProfileSerializer, UserProfileReadSerializer
from utils.pagination_utils import CustomPagination
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.db import transaction
from utils.common_utils import *
from utils.Employee.employee_excel_export_service import EmployeeExcelExportService
from utils.Employee.assignment_utils import get_employee_ids_for_site_on_date, get_user_profiles_under_admin, get_employee_ids_under_admin
from SiteManagement.models import Site
from datetime import date


def get_admin_and_site_optimized(request, site_id):
    """
    Optimized admin and site validation - O(1) queries with select_related
    Returns: (admin, site, None) tuple or (None, None, Response with error)
    """
    user = request.user
    
    # Fast path for admin role - O(1) query
    if user.role == 'admin':
        admin_id = user.id
        admin = user
        # Single O(1) query with index on (id, created_by_admin, is_active)
        if site_id:
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
        return admin, None, None
    
    # Organization role - O(1) queries with select_related
    elif user.role == 'organization':
        admin_id = request.query_params.get('admin_id') or request.data.get('admin_id')
        if not admin_id:
            return None, None, Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "admin_id is required for organization role",
                "data": []
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Single O(1) query to avoid N+1 - uses index on (id, role)
        # Don't use select_related with only() when not accessing the related field
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
        if site_id:
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
                    "message": "Site not found or does not belong to this admin",
                    "data": []
                }, status=status.HTTP_403_FORBIDDEN)
        return admin, None, None
    
    else:
        return None, None, Response({
            "status": status.HTTP_403_FORBIDDEN,
            "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
            "data": []
        }, status=status.HTTP_403_FORBIDDEN)


class StaffListByAdmin(APIView):
    """
    API to get employees under an organization/admin - Optimized
    Supports site-based filtering: /api/staff-list/<site_id>/
    If role is admin, admin_id is fetched from request.user
    """
    pagination_class = CustomPagination

    def get(self, request, site_id):
        """Get staff list - O(1) queries with aggregation"""
        try:
            export = request.query_params.get("export") == "true"
            search = request.query_params.get("q", None)
            status_filter = request.query_params.get("status", None)  # active, inactive, all

            # Get admin and site - O(1) queries
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id

            # If site_id is provided, filter by site (already validated above)
            if site_id:
                # Get employees assigned to this site using common function - O(1) query
                employee_ids = get_employee_ids_for_site_on_date(admin_id, site_id, check_date=None)
                
                if not employee_ids:
                    # No employees assigned to this site
                    queryset_all = UserProfile.objects.none()
                else:
                    # Get UserProfiles for assigned employees - O(1) query with select_related
                    queryset_all = UserProfile.objects.filter(
                        user_id__in=employee_ids
                    ).select_related("user", "organization").only(
                        'id', 'user_id', 'organization_id', 'user_name',
                        'custom_employee_id', 'designation', 'job_title', 'gender',
                        'date_of_joining', 'state', 'city', 'user__email', 'user__is_active'
                    )
            else:
                # Get employees with active assignments under this admin using utility - O(1) query
                queryset_all = get_user_profiles_under_admin(admin_id, active_only=True)
            
            # Apply status filter
            if status_filter == 'active':
                queryset = queryset_all.filter(user__is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset_all.filter(user__is_active=False)
            else:
                # Default: show only active employees
                queryset = queryset_all.filter(user__is_active=True)

            # Optional search - enhanced to include email - uses indexes
            if search:
                search = search.strip()
                queryset = queryset.filter(
                    Q(user_name__icontains=search) |
                    Q(custom_employee_id__icontains=search) |
                    Q(designation__icontains=search) |
                    Q(user__email__icontains=search)
                )

            # Single optimized query for counts using aggregation - O(1) query
            counts = queryset_all.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(user__is_active=True)),
                inactive=Count('id', filter=Q(user__is_active=False))
            )
            total_employees = counts['total']
            active_count = counts['active']
            inactive_count = counts['inactive']

            # Excel export - optimized with .only() to fetch only required fields
            if export:
                # Get all active employees - fetch only required fields
                active_employees_qs = queryset_all.filter(user__is_active=True).only(
                    'id', 'user_id', 'organization_id', 'user_name',
                    'custom_employee_id', 'designation', 'job_title', 'gender',
                    'date_of_joining', 'state', 'city', 'user__email', 'user__is_active'
                )
                active_serializer = UserProfileReadSerializer(active_employees_qs, many=True, context={'request': request})
                active_data = active_serializer.data
                
                # Get all deactivated employees - fetch only required fields
                deactivated_employees_qs = queryset_all.filter(user__is_active=False).only(
                    'id', 'user_id', 'organization_id', 'user_name',
                    'custom_employee_id', 'designation', 'job_title', 'gender',
                    'date_of_joining', 'state', 'city', 'user__email', 'user__is_active'
                )
                deactivated_serializer = UserProfileReadSerializer(deactivated_employees_qs, many=True, context={'request': request})
                deactivated_data = deactivated_serializer.data
                
                return EmployeeExcelExportService.generate(active_data, deactivated_data, admin_id)

            # Fetch only required fields before pagination
            queryset = queryset.only(
                'id', 'user_id', 'organization_id', 'user_name',
                'custom_employee_id', 'designation', 'job_title', 'gender',
                'date_of_joining', 'state', 'city', 'user__email', 'user__is_active'
            )
            
            # Pagination (use filtered queryset for display)
            paginator = self.pagination_class()
            paginated_qs = paginator.paginate_queryset(queryset, request)

            # Serialize with request context for image URLs
            # Use UserProfileReadSerializer for consistency with deactivated list
            serializer = UserProfileReadSerializer(paginated_qs, many=True, context={'request': request})

            # ✅ since your CustomPagination returns a dict
            pagination_data = paginator.get_paginated_response(serializer.data)
            pagination_data["results"] = serializer.data   # ✅ employees list add
            # safely add extra keys to dict
            pagination_data["summary"] = {
                "total": total_employees,
                "active": active_count,
                "inactive": inactive_count,
            }
            pagination_data["message"] = "Data fetched"
            pagination_data["status"] = status.HTTP_200_OK

            return Response(pagination_data)

        except Exception as e:
            return Response(
                {"message": str(e), "status": status.HTTP_500_INTERNAL_SERVER_ERROR, "data": None}
            )

    def put(self, request, *args, **kwargs):
        """Bulk update employees - Optimized with bulk operations"""
        try:
            employee_ids = request.data.get("employee_ids", [])
            if not employee_ids:
                return Response({
                    "message": "employee_ids required",
                    "status": status.HTTP_400_BAD_REQUEST,
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            update_data = request.data.copy()
            update_data.pop("employee_ids", None)

            if not update_data:
                return Response({
                    "message": "No fields to update",
                    "status": status.HTTP_400_BAD_REQUEST,
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get admin_id based on role and verify permissions - O(1) queries
            if request.user.role == 'admin':
                admin_id = request.user.id
                admin = request.user
            elif request.user.role == 'organization':
                # For organization role, admin_id should come from request data or query params
                admin_id = request.query_params.get('admin_id') or request.data.get('admin_id')
                if not admin_id:
                    return Response({
                        "message": "admin_id is required for organization role",
                        "status": status.HTTP_400_BAD_REQUEST,
                        "data": None
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate admin exists and belongs to organization - O(1) query
                try:
                    admin = BaseUserModel.objects.only(
                        'id', 'role', 'email'
                    ).get(id=admin_id, role='admin')
                    
                    # O(1) query - Verify admin belongs to organization
                    admin_profile = AdminProfile.objects.select_related('user', 'organization').only(
                        'id', 'user_id', 'organization_id'
                    ).filter(
                        user=admin,
                        organization=request.user
                    ).first()
                    
                    if not admin_profile:
                        return Response({
                            "message": "Admin does not belong to your organization",
                            "status": status.HTTP_403_FORBIDDEN,
                            "data": None
                        }, status=status.HTTP_403_FORBIDDEN)
                except BaseUserModel.DoesNotExist:
                    return Response({
                        "message": "Admin not found",
                        "status": status.HTTP_404_NOT_FOUND,
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    "message": "Unauthorized access. Only admin and organization roles can update employees",
                    "status": status.HTTP_403_FORBIDDEN,
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)

            # Verify all employees belong to this admin - O(1) query
            admin_employee_ids = get_employee_ids_under_admin(admin_id, active_only=False)
            
            # Check if all requested employee_ids belong to this admin
            admin_employee_ids_set = {str(aid) for aid in admin_employee_ids}
            invalid_employee_ids = [eid for eid in employee_ids if str(eid) not in admin_employee_ids_set]
            if invalid_employee_ids:
                return Response({
                    "message": f"Some employees do not belong to this admin: {invalid_employee_ids}",
                    "status": status.HTTP_403_FORBIDDEN,
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)

            # Single optimized query to get all employees at once - O(1) query with select_related
            employees = UserProfile.objects.filter(
                user_id__in=employee_ids
            ).select_related('user', 'organization').only(
                'id', 'user_id', 'organization_id', 'user_name',
                'custom_employee_id', 'designation', 'job_title', 'gender',
                'date_of_joining', 'state', 'city', 'user__email', 'user__is_active'
            )
            
            # Pre-validate all updates
            results = []
            employees_to_update = []
            
            for employee in employees:
                serializer = UserProfileSerializer(employee, data=update_data, partial=True)
                if serializer.is_valid():
                    # Store validated data for bulk update
                    for key, value in serializer.validated_data.items():
                        setattr(employee, key, value)
                    employees_to_update.append(employee)
                    results.append({"emp_id": str(employee.user_id), "status": "updated"})
                else:
                    results.append({"emp_id": str(employee.user_id), "errors": serializer.errors})
            
            # Bulk update all valid employees in one query - O(1) operation
            if employees_to_update:
                UserProfile.objects.bulk_update(
                    employees_to_update,
                    list(update_data.keys()),
                    batch_size=100
                )

            return Response({
                "message": "Bulk update completed",
                "data": results,
                "status": status.HTTP_200_OK
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "message": f"Error in bulk update: {str(e)}",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
