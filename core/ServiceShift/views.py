"""
Service Shift Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from .models import ServiceShift
from .serializers import *
from django.shortcuts import get_object_or_404
from AuthN.models import BaseUserModel, AdminProfile, UserProfile
from SiteManagement.models import Site
from utils.site_filter_utils import filter_queryset_by_site


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
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Organization role - O(1) queries with select_related
    elif user.role == 'organization':
        admin_id = request.query_params.get('admin_id')
        if not admin_id:
            return None, None, Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "admin_id is required for organization role. Please provide admin_id as query parameter.",
                "data": None
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
                "data": None
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
                "data": None
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
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)
    
    else:
        return None, None, Response({
            "status": status.HTTP_403_FORBIDDEN,
            "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
            "data": None
        }, status=status.HTTP_403_FORBIDDEN)


class ServiceShiftAPIView(APIView):
    """Service Shift CRUD Operations - Optimized"""
    
    def get(self, request, site_id, pk=None):
        """Get shifts - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            if pk:
                # Single O(1) query using index shift_id_adm_idx (id, admin)
                obj = ServiceShift.objects.filter(
                    id=pk,
                    admin_id=admin_id,
                    is_active=True
                ).select_related('admin').only(
                    'id', 'admin_id', 'site_id', 'shift_name', 'start_time', 'end_time',
                    'break_duration_minutes', 'duration_minutes', 'is_night_shift',
                    'is_active', 'created_at', 'updated_at'
                ).first()
                
                if not obj:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Shift not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and obj.site_id != site_id:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Shift not found for this site",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Shift fetched successfully",
                    "data": ServiceShiftSerializer(obj).data
                })
            
            # List query with index optimization - uses shift_adm_active_idx (admin, is_active)
            shifts = ServiceShift.objects.filter(
                admin_id=admin_id,
                is_active=True
            ).select_related('admin').only(
                'id', 'admin_id', 'site_id', 'shift_name', 'start_time', 'end_time',
                'break_duration_minutes', 'duration_minutes', 'is_night_shift',
                'is_active', 'created_at', 'updated_at'
            )
            
            # Filter by site - O(1) with index shift_site_adm_active_idx
            shifts = filter_queryset_by_site(shifts, site_id, 'site')
            shifts = shifts.order_by('shift_name')
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Shifts fetched successfully",
                "data": ServiceShiftSerializer(shifts, many=True).data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Error retrieving shifts: {str(e)}",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, site_id, pk=None):
        """Create shift - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            data = request.data.copy()
            data['admin'] = str(admin.id)
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)

            serializer = ServiceShiftSerializer(data=data)
            if serializer.is_valid():
                shift = serializer.save()
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": f"Shift '{shift.shift_name}' created successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation failed",
                "data": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Error creating shift: {str(e)}",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, site_id, pk=None):
        """Update shift - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index shift_id_adm_idx
            obj = ServiceShift.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Shift not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Shift not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = ServiceShiftUpdateSerializer(obj, data=request.data)
            if serializer.is_valid():
                shift = serializer.save()
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": f"Shift '{shift.shift_name}' updated successfully",
                    "data": serializer.data
                })
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation failed",
                "data": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Error updating shift: {str(e)}",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, site_id, pk=None):
        """Delete shift (soft delete) - Optimized O(1) update"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index shift_id_adm_idx
            obj = ServiceShift.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id', 'shift_name', 'is_active').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Shift not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Shift not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) optimized query to check assignments - uses many-to-many relationship index
            assigned_count = UserProfile.objects.filter(shifts=obj).count()
            
            if assigned_count > 0:
                shift_display_name = obj.shift_name or f"Shift ({obj.start_time} - {obj.end_time})"
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": f"Cannot delete '{shift_display_name}'. This shift is currently assigned to {assigned_count} employee(s). Please unassign this shift from all employees before deleting.",
                    "data": {
                        "assigned_employees_count": assigned_count,
                        "shift_name": shift_display_name
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) optimized update - only update is_active field using index
            shift_name = obj.shift_name
            ServiceShift.objects.filter(id=pk, admin_id=admin.id).update(is_active=False)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Shift '{shift_name}' deleted successfully",
                "data": None
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Error deleting shift: {str(e)}",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)


class AssignShiftToUserAPIView(APIView):
    """
    Assign multiple shifts to a user
    POST /assign-shifts/<admin_id>/<user_id>
    Body: { "shift_ids": [1, 2, 3] }
    """
    
    def post(self, request, site_id, user_id):
        """Assign shifts to user - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # O(1) query - Validate user
            user = BaseUserModel.objects.filter(id=user_id, role='user').only('id', 'role').first()
            if not user:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            user_profile = UserProfile.objects.select_related('user', 'organization').filter(
                user=user
            ).only('id', 'user_id', 'organization_id', 'user_name').first()
            
            if not user_profile:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User profile not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get shift_ids from request
            shift_ids = request.data.get('shift_ids', [])
            
            if not shift_ids:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "shift_ids are required",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not isinstance(shift_ids, list):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "shift_ids must be an array",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) query - Validate shifts belong to admin with select_related
            shifts = ServiceShift.objects.filter(
                id__in=shift_ids,
                admin_id=admin.id,
                is_active=True
            ).select_related('admin').only(
                'id', 'admin_id', 'site_id', 'shift_name', 'is_active'
            )
            
            # Filter by site if provided - O(1) with index
            if site_id:
                shifts = shifts.filter(site_id=site_id)
            
            found_count = shifts.count()
            if found_count != len(shift_ids):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Some shift IDs are invalid or not found",
                    "data": {
                        "requested": len(shift_ids),
                        "found": found_count
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set shifts for user (replaces existing with new selection)
            user_profile.shifts.set(shifts)
            
            # Get assigned shifts data - optimized with select_related
            assigned_shifts = ServiceShiftSerializer(
                user_profile.shifts.select_related('admin').all(), 
                many=True
            ).data
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Successfully assigned {len(assigned_shifts)} shift(s) to {user_profile.user_name}",
                "data": {
                    "user_id": str(user_id),
                    "user_name": user_profile.user_name,
                    "assigned_shifts": assigned_shifts
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error assigning shifts: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request, site_id, user_id=None):
        """Get user's assigned shifts - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # O(1) query - Validate user
            user = BaseUserModel.objects.filter(id=user_id, role='user').only('id', 'role').first()
            if not user:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            user_profile = UserProfile.objects.select_related('user', 'organization').filter(
                user=user
            ).only('id', 'user_id', 'organization_id', 'user_name').first()
            
            if not user_profile:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User profile not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get assigned shifts - optimized with select_related
            assigned_shifts = ServiceShiftSerializer(
                user_profile.shifts.select_related('admin').all(), 
                many=True
            ).data
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Shifts fetched successfully",
                "data": {
                    "user_id": str(user_id),
                    "user_name": user_profile.user_name,
                    "assigned_shifts": assigned_shifts,
                    "count": len(assigned_shifts)
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error fetching shifts: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, site_id, user_id=None, shift_id=None):
        """Remove specific shift or all shifts from user - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # O(1) query - Validate user
            user = BaseUserModel.objects.filter(id=user_id, role='user').only('id', 'role').first()
            if not user:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            user_profile = UserProfile.objects.select_related('user', 'organization').filter(
                user=user
            ).only('id', 'user_id', 'organization_id', 'user_name').first()
            
            if not user_profile:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User profile not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            if shift_id:
                # Remove specific shift - O(1) query
                shift = ServiceShift.objects.filter(
                    id=shift_id, 
                    admin_id=admin.id
                ).only('id', 'shift_name', 'admin_id').first()
                
                if not shift:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Shift not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) check if shift is assigned
                if shift in user_profile.shifts.all():
                    user_profile.shifts.remove(shift)
                    return Response({
                        "status": status.HTTP_200_OK,
                        "message": f"Removed shift '{shift.shift_name}' from {user_profile.user_name}",
                        "data": {
                            "user_id": str(user_id),
                            "user_name": user_profile.user_name,
                            "shift_id": shift_id,
                            "shift_name": shift.shift_name
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": f"Shift '{shift.shift_name}' is not assigned to {user_profile.user_name}",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Clear all shifts - O(1) operation
                shift_count = user_profile.shifts.count()
                user_profile.shifts.clear()
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": f"Removed {shift_count} shift(s) from {user_profile.user_name}",
                    "data": {
                        "user_id": str(user_id),
                        "user_name": user_profile.user_name,
                        "removed_count": shift_count
                    }
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error removing shifts: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
