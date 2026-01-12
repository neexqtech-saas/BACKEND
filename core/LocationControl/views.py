"""
Location Control Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Location
from AuthN.models import AdminProfile, BaseUserModel, UserProfile
from SiteManagement.models import Site
from .serializers import LocationSerializer
from utils.site_filter_utils import filter_queryset_by_site


def get_admin_and_site_optimized(request, site_id):
    """
    Optimized admin and site validation - O(1) queries with select_related
    Returns: (admin, site) tuple or Response with error
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


class LocationAPIView(APIView):
    """Location CRUD Operations - Optimized"""
    
    def get(self, request, site_id, pk=None):
        """Get locations - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            if pk:
                # Single O(1) query using index location_id_adm_idx (id, admin)
                obj = Location.objects.filter(
                    id=pk,
                    admin_id=admin_id,
                    is_active=True
                ).select_related('admin', 'organization').only(
                    'id', 'admin_id', 'site_id', 'organization_id', 'name', 'address',
                    'latitude', 'longitude', 'radius', 'is_active', 'created_at', 'updated_at'
                ).first()
                
                if not obj:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Location not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and obj.site_id != site_id:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Location not found for this site",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Location fetched successfully",
                    "data": LocationSerializer(obj).data
                })
            
            # List query with index optimization - uses location_adm_active_idx (admin, is_active)
            locations = Location.objects.filter(
                admin_id=admin_id,
                is_active=True
            ).select_related('admin', 'organization').only(
                'id', 'admin_id', 'site_id', 'organization_id', 'name', 'address',
                'latitude', 'longitude', 'radius', 'is_active', 'created_at', 'updated_at'
            )
            
            # Filter by site - O(1) with index location_site_adm_active_idx
            locations = filter_queryset_by_site(locations, site_id, 'site')
            locations = locations.order_by('name')
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Locations fetched successfully",
                "data": LocationSerializer(locations, many=True).data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Error retrieving locations: {str(e)}",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, site_id, pk=None):
        """Create location - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # O(1) query - Get admin profile with select_related
            admin_profile = AdminProfile.objects.select_related('organization').filter(
                user_id=admin.id
            ).only('user_id', 'organization_id').first()
            
            if not admin_profile:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Admin not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            data = request.data.copy()
            data['admin'] = str(admin.id)
            data['organization'] = str(admin_profile.organization_id)
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)

            serializer = LocationSerializer(data=data)
            if serializer.is_valid():
                location = serializer.save()
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": f"Location '{location.name}' created successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation failed",
                "data": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error creating location: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, site_id, pk=None):
        """Update location - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index location_id_adm_idx
            obj = Location.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Location not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Location not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = LocationSerializer(obj, data=request.data, partial=True)
            if serializer.is_valid():
                location = serializer.save()
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": f"Location '{location.name}' updated successfully",
                    "data": serializer.data
                })
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation failed",
                "data": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error updating location: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, site_id, pk):
        """Delete location (soft delete) - Optimized O(1) update"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index location_id_adm_idx
            obj = Location.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id', 'name', 'is_active').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Location not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Location not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) optimized query to check assignments - uses many-to-many relationship index
            assigned_count = UserProfile.objects.filter(locations=obj).count()
            
            if assigned_count > 0:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": f"Cannot delete '{obj.name}'. This location is currently assigned to {assigned_count} employee(s). Please unassign this location from all employees before deleting.",
                    "data": {
                        "assigned_employees_count": assigned_count,
                        "location_name": obj.name
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) optimized update - only update is_active field using index
            location_name = obj.name
            Location.objects.filter(id=pk, admin_id=admin.id).update(is_active=False)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Location '{location_name}' deleted successfully",
                "data": None
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error deleting location: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignLocationToUserAPIView(APIView):
    """
    Assign multiple locations to a user
    POST /assign-locations/<admin_id>/<user_id>
    Body: { "location_ids": [1, 2, 3] }
    """
    
    def post(self, request, site_id, user_id=None):
        """Assign locations to user - Optimized"""
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
            
            # Get location_ids from request
            location_ids = request.data.get('location_ids', [])
            
            if not location_ids:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "location_ids are required",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not isinstance(location_ids, list):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "location_ids must be an array",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) query - Validate locations belong to admin with select_related
            locations = Location.objects.filter(
                id__in=location_ids,
                admin_id=admin.id,
                is_active=True
            ).select_related('admin', 'organization').only(
                'id', 'admin_id', 'site_id', 'name', 'is_active'
            )
            
            # Filter by site if provided - O(1) with index
            if site_id:
                locations = locations.filter(site_id=site_id)
            
            found_count = locations.count()
            if found_count != len(location_ids):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Some location IDs are invalid or not found",
                    "data": {
                        "requested": len(location_ids),
                        "found": found_count
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set locations for user (replaces existing with new selection)
            user_profile.locations.set(locations)
            
            # Get assigned locations data - optimized with select_related
            assigned_locations = LocationSerializer(
                user_profile.locations.select_related('admin', 'organization').all(), 
                many=True
            ).data
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Successfully assigned {len(assigned_locations)} location(s) to {user_profile.user_name}",
                "data": {
                    "user_id": str(user_id),
                    "user_name": user_profile.user_name,
                    "assigned_locations": assigned_locations
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error assigning locations: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request, site_id, user_id):
        """Get user's assigned locations - Optimized"""
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
            
            # Get assigned locations - optimized with select_related
            assigned_locations = LocationSerializer(
                user_profile.locations.select_related('admin', 'organization').all(), 
                many=True
            ).data
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Locations fetched successfully",
                "data": {
                    "user_id": str(user_id),
                    "user_name": user_profile.user_name,
                    "assigned_locations": assigned_locations,
                    "count": len(assigned_locations)
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error fetching locations: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, site_id, user_id=None, location_id=None):
        """Remove specific location or all locations from user - Optimized"""
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
            
            if location_id:
                # Remove specific location - O(1) query
                location = Location.objects.filter(
                    id=location_id, 
                    admin_id=admin.id
                ).only('id', 'name', 'admin_id').first()
                
                if not location:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Location not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) check if location is assigned
                if location in user_profile.locations.all():
                    user_profile.locations.remove(location)
                    return Response({
                        "status": status.HTTP_200_OK,
                        "message": f"Removed location '{location.name}' from {user_profile.user_name}",
                        "data": {
                            "user_id": str(user_id),
                            "user_name": user_profile.user_name,
                            "location_id": location_id,
                            "location_name": location.name
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": f"Location '{location.name}' is not assigned to {user_profile.user_name}",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Clear all locations - O(1) operation
                location_count = user_profile.locations.count()
                user_profile.locations.clear()
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": f"Removed {location_count} location(s) from {user_profile.user_name}",
                    "data": {
                        "user_id": str(user_id),
                        "user_name": user_profile.user_name,
                        "removed_count": location_count
                    }
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error removing locations: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
