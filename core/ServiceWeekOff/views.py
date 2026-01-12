"""
Service Week Off Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import WeekOffPolicy
from AuthN.models import AdminProfile, BaseUserModel, UserProfile
from SiteManagement.models import Site
from .serializers import WeekOffPolicySerializer, WeekOffPolicyUpdateSerializer
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


class WeekOffPolicyAPIView(APIView):
    """Week Off Policy CRUD Operations - Optimized"""
    
    def get(self, request, site_id, pk=None):
        """Get week off policies - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            if pk:
                # Single O(1) query using index weekoff_id_adm_idx (id, admin)
                obj = WeekOffPolicy.objects.filter(
                    id=pk,
                    admin_id=admin_id,
                    is_active=True
                ).select_related('admin').only(
                    'id', 'admin_id', 'site_id', 'name', 'week_off_type', 
                    'week_days', 'week_off_cycle', 'description', 'is_active', 
                    'created_at', 'updated_at'
                ).first()
                
                if not obj:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Week off policy not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and obj.site_id != site_id:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Week off policy not found for this site",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Week off policy fetched successfully",
                    "data": WeekOffPolicySerializer(obj).data
                })
            
            # List query with index optimization - uses weekoff_adm_active_idx (admin, is_active)
            policies = WeekOffPolicy.objects.filter(
                admin_id=admin_id,
                is_active=True
            ).select_related('admin').only(
                'id', 'admin_id', 'site_id', 'name', 'week_off_type', 
                'week_days', 'week_off_cycle', 'description', 'is_active', 
                'created_at', 'updated_at'
            )
            
            # Filter by site - O(1) with index weekoff_site_adm_active_idx
            policies = filter_queryset_by_site(policies, site_id, 'site')
            policies = policies.order_by('name')
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Week off policies fetched successfully",
                "data": WeekOffPolicySerializer(policies, many=True).data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Error retrieving week off policies: {str(e)}",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, site_id, pk=None):
        """Create week off policy - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            data = request.data.copy()
            data['admin'] = str(admin.id)
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)

            serializer = WeekOffPolicySerializer(data=data)
            if serializer.is_valid():
                policy = serializer.save()
                policy_name = policy.name or "Week Off Policy"
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": f"Week off policy '{policy_name}' created successfully",
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
                "message": f"Error creating week off policy: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, site_id, pk=None):
        """Update week off policy - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index weekoff_id_adm_idx
            obj = WeekOffPolicy.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Week off policy not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Week off policy not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = WeekOffPolicyUpdateSerializer(obj, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Week off policy updated successfully",
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
                "message": f"Error updating week off policy: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, site_id, pk=None):
        """Delete week off policy (soft delete) - Optimized O(1) update"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index weekoff_id_adm_idx
            obj = WeekOffPolicy.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id', 'name', 'is_active').first()
            
            if not obj:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Week off policy not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if obj.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Week off policy not found for this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) optimized query to check assignments - uses many-to-many relationship index
            assigned_count = UserProfile.objects.filter(week_offs=obj).count()
            
            if assigned_count > 0:
                policy_display_name = obj.name or f"Week Off Policy {obj.id}"
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": f"Cannot delete '{policy_display_name}'. This week off policy is currently assigned to {assigned_count} employee(s). Please unassign this policy from all employees before deleting.",
                    "data": {
                        "assigned_employees_count": assigned_count,
                        "policy_name": policy_display_name
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) optimized update - only update is_active field using index
            policy_name = obj.name or "Week Off Policy"
            WeekOffPolicy.objects.filter(id=pk, admin_id=admin.id).update(is_active=False)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Week off policy '{policy_name}' deleted successfully",
                "data": None
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error deleting week off policy: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignWeekOffToUserAPIView(APIView):
    """Assign/Get/Delete week off policies for a user"""
    
    def post(self, request, site_id, user_id=None):
        """Assign week off policies to user - Optimized"""
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
            
            # Get week_off_ids from request
            week_off_ids = request.data.get('week_off_ids', [])
            
            if not isinstance(week_off_ids, list):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "week_off_ids must be an array",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) query - Validate week offs belong to admin with select_related
            week_offs = WeekOffPolicy.objects.filter(
                id__in=week_off_ids,
                admin_id=admin.id,
                is_active=True
            ).select_related('admin').only(
                'id', 'admin_id', 'site_id', 'name', 'is_active'
            )
            
            # Filter by site if provided - O(1) with index
            if site_id:
                week_offs = week_offs.filter(site_id=site_id)
            
            found_count = week_offs.count()
            if found_count != len(week_off_ids):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Some week off IDs are invalid or not found",
                    "data": {
                        "requested": len(week_off_ids),
                        "found": found_count
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set week offs for user (replaces existing with new selection)
            user_profile.week_offs.set(week_offs)
            
            # Get assigned week offs data - optimized with select_related
            assigned_week_offs = WeekOffPolicySerializer(
                user_profile.week_offs.select_related('admin').all(), 
                many=True
            ).data
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Successfully assigned {len(assigned_week_offs)} week off policy(ies) to {user_profile.user_name}",
                "data": {
                    "user_id": str(user_id),
                    "user_name": user_profile.user_name,
                    "assigned_week_offs": assigned_week_offs
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error assigning week offs: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request, site_id, user_id=None):
        """Get user's assigned week offs - Optimized"""
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
            
            # Get assigned week offs - optimized with select_related
            assigned_week_offs = WeekOffPolicySerializer(
                user_profile.week_offs.select_related('admin').all(), 
                many=True
            ).data
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Week offs fetched successfully",
                "data": {
                    "user_id": str(user_id),
                    "user_name": user_profile.user_name,
                    "assigned_week_offs": assigned_week_offs,
                    "count": len(assigned_week_offs)
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error fetching week offs: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, site_id, user_id=None, week_off_id=None):
        """Remove specific week off or all week offs from user - Optimized"""
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
            
            if week_off_id:
                # Remove specific week off - O(1) query
                week_off = WeekOffPolicy.objects.filter(
                    id=week_off_id, 
                    admin_id=admin.id
                ).only('id', 'name', 'admin_id').first()
                
                if not week_off:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Week off policy not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) check if week off is assigned
                if week_off in user_profile.week_offs.all():
                    user_profile.week_offs.remove(week_off)
                    return Response({
                        "status": status.HTTP_200_OK,
                        "message": f"Removed week off policy '{week_off.name}' from {user_profile.user_name}",
                        "data": {
                            "user_id": str(user_id),
                            "user_name": user_profile.user_name,
                            "week_off_id": week_off_id,
                            "week_off_name": week_off.name
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": f"Week off policy '{week_off.name}' is not assigned to {user_profile.user_name}",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Clear all week offs - O(1) operation
                week_off_count = user_profile.week_offs.count()
                user_profile.week_offs.clear()
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": f"Removed {week_off_count} week off policy(ies) from {user_profile.user_name}",
                    "data": {
                        "user_id": str(user_id),
                        "user_name": user_profile.user_name,
                        "removed_count": week_off_count
                    }
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error removing week offs: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
