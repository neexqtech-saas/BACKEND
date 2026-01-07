"""
Holiday Management Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Holiday
from .serializers import HolidaySerializer, HolidayUpdateSerializer
from AuthN.models import AdminProfile, BaseUserModel
from SiteManagement.models import Site
from utils.site_filter_utils import filter_queryset_by_site


def get_admin_and_site_for_holiday(request, site_id):
    """
    Optimized admin and site validation - O(1) queries with select_related
    Handles admin, organization, and user roles
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
                'message': 'Site not found or you don\'t have permission to access this site',
                'data': [],
                'status': status.HTTP_403_FORBIDDEN
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Organization role - O(1) queries with select_related
    elif user.role == 'organization':
        admin_id = request.query_params.get('admin_id')
        if not admin_id:
            return None, None, Response({
                'message': 'admin_id is required for organization role. Please provide admin_id as query parameter.',
                'data': [],
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Single O(1) query with select_related to avoid N+1 - uses index on (id, role)
        try:
            admin = BaseUserModel.objects.select_related('own_admin_profile').only(
                'id', 'role', 'email'
            ).get(id=admin_id, role='admin')
        except BaseUserModel.DoesNotExist:
            return None, None, Response({
                'message': 'Admin not found',
                'data': [],
                'status': status.HTTP_404_NOT_FOUND
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
                'message': 'Admin does not belong to your organization',
                'data': [],
                'status': status.HTTP_403_FORBIDDEN
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
                'message': 'Site not found or you don\'t have permission to access this site',
                'data': [],
                'status': status.HTTP_403_FORBIDDEN
            }, status=status.HTTP_403_FORBIDDEN)
    
    # User role - O(1) queries with select_related
    elif user.role == 'user':
        # O(1) query - Get admin from current assignment using utility
        from utils.Employee.assignment_utils import get_current_admin_for_employee
        admin = get_current_admin_for_employee(user)
        if not admin:
            return None, None, Response({
                'message': 'You are not assigned to any admin. Please contact your administrator.',
                'data': [],
                'status': status.HTTP_403_FORBIDDEN
            }, status=status.HTTP_403_FORBIDDEN)
        
        admin_id = admin.id
        # O(1) query - Validate site exists (for employees, just check if site exists and is active)
        try:
            site = Site.objects.only('id', 'site_name', 'is_active').get(
                id=site_id, 
                is_active=True
            )
            return admin, site, None
        except Site.DoesNotExist:
            return None, None, Response({
                'message': 'Site not found',
                'data': [],
                'status': status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
    
    else:
        return None, None, Response({
            'message': 'Unauthorized access. Only admin, organization, and user roles can access this endpoint',
            'data': [],
            'status': status.HTTP_403_FORBIDDEN
        }, status=status.HTTP_403_FORBIDDEN)


class HolidayAPIView(APIView):
    """Holiday CRUD Operations - Optimized"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, site_id, pk=None):
        """Get holidays - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_for_holiday(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            if pk:
                # Single O(1) query using index holiday_id_adm_idx (id, admin)
                holiday = Holiday.objects.filter(
                    id=pk,
                    admin_id=admin_id,
                    is_active=True
                ).only(
                    'id', 'admin_id', 'organization_id', 'site_id', 'name', 'holiday_date', 
                    'is_optional', 'is_active', 'created_at', 'updated_at'
                ).first()
                
                if not holiday:
                    return Response({
                        'message': 'Holiday not found',
                        'data': None,
                        'status': status.HTTP_404_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and holiday.site_id and holiday.site_id != site_id:
                    return Response({
                        'message': 'Holiday not found for this site',
                        'data': None,
                        'status': status.HTTP_404_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)
                
                serializer = HolidaySerializer(holiday)
                # For single object, wrap in array for frontend compatibility
                return Response({
                    'message': 'Holiday retrieved successfully',
                    'data': [serializer.data] if serializer.data else [],
                    'status': status.HTTP_200_OK
                }, status=status.HTTP_200_OK)
            
            # List query with index optimization - uses holiday_adm_active_date_idx (admin, is_active, holiday_date)
            holidays = Holiday.objects.filter(
                admin_id=admin_id,
                is_active=True
            ).only(
                'id', 'admin_id', 'organization_id', 'site_id', 'name', 'holiday_date', 
                'is_optional', 'is_active', 'created_at', 'updated_at'
            )
            
            # Filter by site - O(1) with index
            holidays = filter_queryset_by_site(holidays, site_id, 'site')
            holidays = holidays.order_by('-holiday_date')
            
            serializer = HolidaySerializer(holidays, many=True)
            # Ensure data is always an array for frontend compatibility
            data_array = serializer.data if isinstance(serializer.data, list) else []
            return Response({
                'message': 'Holidays retrieved successfully',
                'data': data_array,
                'status': status.HTTP_200_OK
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'message': f'Error retrieving holidays: {str(e)}',
                'data': [],  # Always return array for frontend compatibility
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, site_id, pk=None):
        """Create holiday - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_for_holiday(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            # O(1) query - Get admin profile with select_related
            admin_profile = AdminProfile.objects.select_related('organization').filter(
                user_id=admin_id
            ).only('user_id', 'organization_id').first()
            
            if not admin_profile:
                return Response({
                    'message': 'Admin not found',
                    'data': [],  # Always return array for frontend compatibility
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            data = request.data.copy()
            data['admin'] = admin_id
            data['organization'] = admin_profile.organization_id
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)

            serializer = HolidaySerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Holiday created successfully',
                    'data': [serializer.data] if serializer.data else [],
                    'status': status.HTTP_201_CREATED
                }, status=status.HTTP_201_CREATED)
            return Response({
                'message': 'Validation error',
                'data': [],  # Always return array for frontend compatibility
                'errors': serializer.errors,
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'message': f'Error creating holiday: {str(e)}',
                'data': [],  # Always return array for frontend compatibility
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, site_id, pk=None):
        """Update holiday - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_for_holiday(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index holiday_id_adm_idx
            holiday = Holiday.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not holiday:
                return Response({
                    'message': 'Holiday not found',
                    'data': [],  # Always return array for frontend compatibility
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and holiday.site_id != site_id:
                return Response({
                    'message': 'Holiday not found for this site',
                    'data': [],
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = HolidayUpdateSerializer(holiday, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Holiday updated successfully',
                    'data': [serializer.data] if serializer.data else [],
                    'status': status.HTTP_200_OK
                }, status=status.HTTP_200_OK)
            return Response({
                'message': 'Validation error',
                'data': [],  # Always return array for frontend compatibility
                'errors': serializer.errors,
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'message': f'Error updating holiday: {str(e)}',
                'data': [],  # Always return array for frontend compatibility
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, site_id, pk=None):
        """Partial update holiday - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_for_holiday(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index holiday_id_adm_idx
            holiday = Holiday.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not holiday:
                return Response({
                    'message': 'Holiday not found',
                    'data': [],  # Always return array for frontend compatibility
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and holiday.site_id != site_id:
                return Response({
                    'message': 'Holiday not found for this site',
                    'data': [],
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = HolidaySerializer(holiday, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Holiday updated successfully',
                    'data': [serializer.data] if serializer.data else [],
                    'status': status.HTTP_200_OK
                }, status=status.HTTP_200_OK)
            return Response({
                'message': 'Validation error',
                'data': [],  # Always return array for frontend compatibility
                'errors': serializer.errors,
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'message': f'Error updating holiday: {str(e)}',
                'data': [],  # Always return array for frontend compatibility
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, site_id, pk=None):
        """Delete holiday (soft delete) - Optimized O(1) update"""
        try:
            admin, site, error_response = get_admin_and_site_for_holiday(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query to check existence using index
            holiday = Holiday.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id', 'is_active').first()
            
            if not holiday:
                return Response({
                    'message': 'Holiday not found',
                    'data': [],  # Always return array for frontend compatibility
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and holiday.site_id != site_id:
                return Response({
                    'message': 'Holiday not found for this site',
                    'data': [],
                    'status': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) optimized update - only update is_active field using index
            Holiday.objects.filter(id=pk, admin_id=admin.id).update(is_active=False)
            
            return Response({
                'message': 'Holiday deleted successfully',
                'data': [],  # Always return array for frontend compatibility
                'status': status.HTTP_200_OK
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'message': f'Error deleting holiday: {str(e)}',
                'data': None,
                'status': status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
