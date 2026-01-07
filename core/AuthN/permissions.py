"""
Custom Permission Classes for AuthN Module
==========================================

These permission classes control access to different API endpoints based on user roles.

Time Complexity: O(1) - Constant time permission checks
Space Complexity: O(1) - No additional space required
"""

from rest_framework import permissions

class IsSystemOwner(permissions.BasePermission):
    """
    Permission class that allows access only to System Owner role.
    
    Usage:
        permission_classes = [IsSystemOwner]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        """Check if user is authenticated and has system_owner role."""
        return request.user.is_authenticated and request.user.role == "system_owner"

class IsSystemOwnerOrOrganization(permissions.BasePermission):
    """
    Permission class that allows access to System Owner or Organization roles.
    
    Usage:
        permission_classes = [IsSystemOwnerOrOrganization]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        """Check if user is authenticated and has system_owner or organization role."""
        return request.user.is_authenticated and request.user.role in ["system_owner", "organization"]

class IsSystemOwnerOrOrganizationOrAdmin(permissions.BasePermission):
    """
    Permission class that allows access to System Owner, Organization, or Admin roles.
    
    Usage:
        permission_classes = [IsSystemOwnerOrOrganizationOrAdmin]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        """Check if user is authenticated and has system_owner, organization, or admin role."""
        return request.user.is_authenticated and request.user.role in ["system_owner", "organization", "admin"]


class IsOrganizationOrAdmin(permissions.BasePermission):
    """
    Permission class that allows access to System Owner, Organization, or Admin roles.
    
    Usage:
        permission_classes = [IsSystemOwnerOrOrganizationOrAdmin]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        """Check if user is authenticated and has system_owner, organization, or admin role."""
        return request.user.is_authenticated and request.user.role in ["organization", "admin"]

class IsOrganization(permissions.BasePermission):
    """
    Permission class that allows access only to Organization role.
    
    Usage:
        permission_classes = [IsOrganization]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        print(request.user.role)
        print(request.user.is_authenticated)
        print(request.user.role == "organization")
        print(request.user.is_authenticated and request.user.role == "organization")    
        """Check if user is authenticated and has organization role."""
        return request.user.is_authenticated and request.user.role == "organization"

class IsAdmin(permissions.BasePermission):
    """
    Permission class that allows access only to Admin role.
    
    Usage:
        permission_classes = [IsAdmin]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        """Check if user is authenticated and has admin role."""
        return request.user.is_authenticated and request.user.role == "admin"

class IsUser(permissions.BasePermission):
    """
    Permission class that allows access only to User role.
    
    Usage:
        permission_classes = [IsUser]
    
    Time Complexity: O(1)
    """
    def has_permission(self, request, view):
        """Check if user is authenticated and has user role."""
        print("user", request.user)
        print("user role", request.user.role)
        print("user is authenticated", request.user.is_authenticated)
        print("user role == user", request.user.role == "user")
        print("user is authenticated and user role == user", request.user.is_authenticated and request.user.role == "user") 
        return request.user.is_authenticated and request.user.role == "user"


class CanUpdateOwnOrAnyUser(permissions.BasePermission):
    """
    Base permission class that allows users to update their own data,
    and System Owners/Organizations/Admins to update any user's data.
    
    This is a reusable permission for operations like:
    - Changing password
    - Updating FCM token
    - And other similar operations where users can update their own data,
      while admins/orgs/system_owners can update any user's data
    
    Usage:
        permission_classes = [IsAuthenticated, CanUpdateOwnOrAnyUser]
    
    Time Complexity: O(1) - Constant time comparisons.
    Space Complexity: O(1) - No additional space required.
    """
    def has_permission(self, request, view):
        """
        Check if the user is authenticated. Object-level permission will handle further checks.
        
        Args:
            request: The current request.
            view: The view instance.
        
        Returns:
            bool: True if user is authenticated, False otherwise.
        """
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """
        Check if the requesting user has permission to update the given object (BaseUserModel instance).
        
        Permission Logic:
        - User can update their own data (obj.id == request.user.id)
        - System Owner/Organization/Admin can update any user's data
        
        Args:
            request: The current request.
            view: The view instance.
            obj: The BaseUserModel instance being accessed.
        
        Returns:
            bool: True if the user has permission, False otherwise.
        
        Time Complexity: O(1) - Constant time comparisons.
        """
        current_user = request.user
        
        # Allow if:
        # 1. The requesting user is updating their own data.
        # 2. The requesting user has a 'system_owner', 'organization', or 'admin' role.
        is_own_data = obj.id == current_user.id
        has_admin_access = current_user.role in ['system_owner', 'organization', 'admin']
        
        return is_own_data or has_admin_access

