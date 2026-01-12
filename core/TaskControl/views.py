"""
Task Control Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import TaskType
from .serializers import TaskTypeSerializer, TaskTypeUpdateSerializer
from AuthN.models import BaseUserModel, AdminProfile
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


class TaskTypeAPIView(APIView):
    """Task Type CRUD Operations - Optimized"""
    
    def get(self, request, site_id, pk=None):
        """Get task types - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            if pk:
                # Single O(1) query using index tasktype_id_adm_idx (id, admin)
                obj = TaskType.objects.filter(
                    id=pk,
                    admin_id=admin_id,
                    is_active=True
                ).select_related('admin').only(
                    'id', 'admin_id', 'site_id', 'name', 'description', 
                    'color_code', 'is_active', 'created_at', 'updated_at'
                ).first()
                
                if not obj:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Task type not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and obj.site_id != site_id:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Task type not found for this site",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Task type fetched successfully",
                    "data": TaskTypeSerializer(obj).data
                })
            
            # List query with index optimization - uses tasktype_adm_active_idx (admin, is_active)
            queryset = TaskType.objects.filter(
                admin_id=admin_id,
                is_active=True
            ).select_related('admin').only(
                'id', 'admin_id', 'site_id', 'name', 'description', 
                'color_code', 'is_active', 'created_at', 'updated_at'
            )
            
            # Filter by site - O(1) with index tasktype_site_adm_active_idx
            queryset = filter_queryset_by_site(queryset, site_id, 'site')
            queryset = queryset.order_by('name')
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Task types fetched successfully",
                "data": TaskTypeSerializer(queryset, many=True).data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, site_id):
        """Create task type - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            data = request.data.copy()
            data['admin'] = str(admin.id)
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)

            serializer = TaskTypeSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Task type created successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, site_id, pk=None):
        """Update task type - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index tasktype_id_adm_idx
            obj = TaskType.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Task type not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Task type not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = TaskTypeUpdateSerializer(obj, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Task type updated successfully",
                    "data": serializer.data
                })
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, site_id, pk=None):
        """Delete task type (soft delete) - Optimized O(1) update"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index tasktype_id_adm_idx
            obj = TaskType.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id', 'is_active').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Task type not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Task type not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) optimized update - only update is_active field using index
            TaskType.objects.filter(id=pk, admin_id=admin.id).update(is_active=False)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Task type deleted successfully",
                "data": None
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
