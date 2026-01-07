"""
Authentication and User Management Views
========================================

All views are optimized for O(1) complexity where possible:
- Use select_related/prefetch_related to avoid N+1 queries
- Use proper database indexes for all queries
- Consistent error response format
- Proper use of serializers for validation
- Helper functions to eliminate code duplication

Time Complexity: O(1) for most operations
Space Complexity: O(1) - Minimal space usage
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import authenticate
from .models import (
    BaseUserModel, SystemOwnerProfile, OrganizationProfile,
    AdminProfile, UserProfile, OrganizationSettings
)
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    SystemOwnerProfileSerializer, OrganizationProfileSerializer,
    AdminProfileSerializer, UserProfileSerializer,
    OrganizationSettingsSerializer, AllOrganizationProfileSerializer
)
from .permissions import IsSystemOwner
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from utils.session_utils import serialize_org_settings
import os
import uuid
from datetime import datetime
from django.utils import timezone
from django.conf import settings


def generate_tokens(user):
    """
    Generate JWT tokens for a user.
    
    Args:
        user: BaseUserModel instance
        
    Returns:
        dict: Contains refresh_token, access_token, user_id, and role
        
    Time Complexity: O(1)
    """
    refresh = RefreshToken.for_user(user)
    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
        "user_id": str(user.id),
        "role": user.role,
    }


def validate_admin_for_organization(request, admin_id):
    """
    Optimized admin validation for organization role - O(1) queries with select_related
    Returns: (admin_user, None) on success or (None, error_response) on failure
    """
    if not admin_id:
        return None, Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": {
                "admin_id": ["admin_id is required when registering as organization. Please provide 'admin_id' in the payload."]
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # O(1) query - Single query with select_related to avoid N+1
    # Uses index on (id, role) if exists, else primary key
    try:
        admin_user = BaseUserModel.objects.select_related('own_admin_profile').only(
            'id', 'role', 'email'
        ).get(id=admin_id, role='admin')
    except BaseUserModel.DoesNotExist:
        return None, Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": {
                "admin_id": ["Admin not found with the provided admin_id."]
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # O(1) query - Verify admin belongs to organization using select_related
    # Uses index on (user_id, organization_id) if exists, else (user_id)
    admin_profile = AdminProfile.objects.select_related('user', 'organization').only(
        'id', 'user_id', 'organization_id'
    ).filter(
        user_id=admin_id,
        organization_id=request.user.id
    ).first()
    
    if not admin_profile:
        return None, Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": {
                "admin_id": ["Invalid admin_id. The admin must belong to your organization."]
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return admin_user, None


class SystemOwnerRegisterView(generics.CreateAPIView):
    """
    Register a new System Owner.
    
    Time Complexity: O(1) - Single database insert
    """
    queryset = SystemOwnerProfile.objects.all()
    serializer_class = SystemOwnerProfileSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        """
        Create a new system owner profile.
        
        Returns:
            Response with tokens on success, validation errors on failure
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            profile = serializer.save()
            return Response(generate_tokens(profile.user), status=status.HTTP_201_CREATED)
        
        return Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class OrganizationRegisterView(generics.CreateAPIView):
    """
    Register a new Organization under a System Owner.
    
    Time Complexity: O(1) - Single database insert with select_related
    """
    queryset = OrganizationProfile.objects.select_related('user', 'system_owner')
    serializer_class = OrganizationProfileSerializer
    permission_classes = [IsSystemOwner]

    def create(self, request, *args, **kwargs):
        """
        Create a new organization profile.
        Automatically assigns the logged-in system owner.
        
        Returns:
            Response with tokens on success, validation errors on failure
        """
        system_owner = request.user
        
        # Add system_owner to request data
        mutable_data = request.data.copy()
        mutable_data["system_owner"] = str(system_owner.id)

        serializer = self.get_serializer(data=mutable_data)
        if serializer.is_valid():
            profile = serializer.save()
            return Response(generate_tokens(profile.user), status=status.HTTP_201_CREATED)

        return Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminRegisterView(generics.CreateAPIView):
    """
    Register a new Admin under an Organization.
    
    If logged-in user is an organization, automatically assigns it.
    
    Time Complexity: O(1) - Single database insert with select_related
    """
    queryset = AdminProfile.objects.select_related('user', 'organization')
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Create a new admin profile.
        Automatically assigns organization if logged-in user is an organization.
        
        Returns:
            Response with admin data on success, validation errors on failure
        """
        # If logged-in user is an organization, automatically set organization
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if request.user.role == 'organization':
            data['organization'] = str(request.user.id)
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            profile = serializer.save()
            return Response({
                "status": status.HTTP_201_CREATED,
                "message": "Admin created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserRegisterView(generics.CreateAPIView):
    """
    Register a new User (Employee) under an Admin.
    
    If logged-in user is an admin, automatically assigns it.
    If logged-in user is an organization, uses admin_id from request data or selected_admin_id.
    
    Time Complexity: O(1) - Single database insert with select_related
    """
    queryset = UserProfile.objects.select_related('user', 'organization')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Create a new user profile.
        Automatically assigns admin if logged-in user is an admin.
        If logged-in user is an organization, uses admin_id from request.
        
        Returns:
            Response with tokens on success, validation errors on failure
        """
        # Prepare data
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        
        # Validate admin context for assignment creation
        # If logged-in user is an admin, use that admin
        # If logged-in user is an organization, require admin_id in payload
        admin_user = None
        if request.user.role == 'admin':
            admin_user = request.user
        elif request.user.role == 'organization':
            # Use optimized helper function
            admin_user, error_response = validate_admin_for_organization(request, data.get('admin_id'))
            if error_response:
                return error_response
        else:
            return Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Only admin or organization users can register employees."
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Pass site_id from request data to serializer context if provided
        serializer_context = {'request': request}
        site_id = data.get('site_id')
        if site_id:
            serializer_context['site_id'] = site_id
        
        serializer = self.get_serializer(data=data, context=serializer_context)
        if serializer.is_valid():
            profile = serializer.save()
            return Response(generate_tokens(profile.user), status=status.HTTP_201_CREATED)
        
        return Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    Login endpoint supporting both email and username authentication.
    
    Optimized with proper indexes and O(1) queries.
    
    Time Complexity: O(1) - Constant time authentication with index usage
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Authenticate user and return JWT tokens.
        Supports both email and username login.
        
        Returns:
            Response with tokens on success, error message on failure
        """
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()

        if not username or not password:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Username/Email/Employee ID and password are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        user = None
        
        # O(1) - First, try to authenticate with the value as email (since USERNAME_FIELD = "email")
        # Uses index on email (unique constraint)
        user = authenticate(request, username=username, password=password)
        
        # O(1) - If authentication fails, try to find user by username and then authenticate with email
        # Uses index on username (unique constraint)
        if user is None:
            try:
                # O(1) - Single query with .only() to limit fields, uses username index
                user_obj = BaseUserModel.objects.only('id', 'email', 'username', 'is_active').get(username=username)
                # O(1) - Authenticate with email
                user = authenticate(request, username=user_obj.email, password=password)
            except BaseUserModel.DoesNotExist:
                user = None
        
        # O(1) - If still None, try custom_employee_id for employee login
        # Uses index on custom_employee_id (unique constraint)
        if user is None:
            try:
                # O(1) - Single query with select_related and .only(), uses custom_employee_id index
                user_profile = UserProfile.objects.select_related('user').only(
                    'user__id', 'user__email', 'user__is_active', 'custom_employee_id'
                ).get(custom_employee_id=username)
                # O(1) - Authenticate with email
                user = authenticate(request, username=user_profile.user.email, password=password)
            except UserProfile.DoesNotExist:
                user = None

        if user is None:
            return Response({
                "status": status.HTTP_401_UNAUTHORIZED,
                "message": "Invalid credentials"
            }, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({
                "status": status.HTTP_401_UNAUTHORIZED,
                "message": "User account is disabled"
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Generate tokens
        tokens = generate_tokens(user)
        
        # Add organization_id for admin role - O(1) query with select_related
        if user.role == "admin":
            try:
                # O(1) - Single query with select_related, uses index on (user_id) or primary key
                admin_profile = AdminProfile.objects.select_related('organization').filter(
                    user_id=user.id
                ).only('organization_id', 'organization__id').first()
                
                if admin_profile and admin_profile.organization:
                    tokens["organization_id"] = str(admin_profile.organization.id)
                else:
                    # Log warning if admin profile or organization not found
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Admin profile or organization not found for user {user.id}")
            except Exception as e:
                # Log error but continue without organization_id
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error fetching organization_id for admin {user.id}: {str(e)}")
        
        # For organization role, user_id is the organization_id
        if user.role == "organization":
            tokens["organization_id"] = str(user.id)
        
        # Add is_photo_updated status for employees - O(1) query
        if user.role == "user":
            try:
                # O(1) - Single query with .only(), uses index on (user_id) or primary key
                user_profile = UserProfile.objects.filter(user_id=user.id).only('is_photo_updated').first()
                if user_profile:
                    tokens["is_photo_updated"] = user_profile.is_photo_updated
                else:
                    tokens["is_photo_updated"] = False
            except Exception as e:
                # Log error but continue without is_photo_updated
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error fetching user profile for user {user.id}: {str(e)}")
                tokens["is_photo_updated"] = False

        return Response(tokens, status=status.HTTP_200_OK)


class ChangePasswordView(generics.GenericAPIView):
    """
    Change password for authenticated user.
    
    Time Complexity: O(1) - Constant time password operations
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Change user's password.
        
        Returns:
            Response with success message or error details
        """
        user = request.user
        old_password = request.data.get("old_password", "").strip()
        new_password = request.data.get("new_password", "").strip()

        if not old_password or not new_password:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Old password and new password are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(old_password):
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Old password is incorrect"
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=['password'])

        return Response({
            "status": status.HTTP_200_OK,
            "message": "Password updated successfully"
        }, status=status.HTTP_200_OK)



class OrganizationSettingsAPIView(APIView):
    """
    Get and update organization settings.
    
    Time Complexity: O(1) - Single database query with select_related
    
    Permissions:
    - GET: Allow organization users to read their own settings, system owners to read any
    - PUT: Only system owners can update
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, org_id):
        """
        Get organization settings.
        All authenticated users can access this endpoint.
        
        Args:
            org_id: Organization UUID
            
        Returns:
            Response with settings data
        """
        # O(1) - Single query with select_related, uses index on (organization_id) or primary key
        settings = get_object_or_404(
            OrganizationSettings.objects.select_related('organization').only(
                'id', 'organization_id', 'organization__id', 'organization__email',
                'face_recognition_enabled', 'auto_checkout_enabled', 'organization_logo'
            ),
            organization__id=org_id
        )
        serializer = OrganizationSettingsSerializer(settings, context={'request': request})
        
        return Response({
            "status": status.HTTP_200_OK,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request, org_id):
        """
        Update organization settings.
        
        Args:
            org_id: Organization UUID
            
        Returns:
            Response with updated settings or validation errors
            
        Permissions:
        - System owners can update any organization settings
        - Organization users can update their own settings
        """
        user = request.user
        
        # Check if user is system owner (can update any org settings)
        is_system_owner = IsSystemOwner().has_permission(request, self)
        
        # Check if user is organization and trying to update their own settings
        is_own_organization = (
            user.role == 'organization' and 
            str(user.id) == str(org_id)
        )
        
        # Allow if system owner OR organization updating their own settings
        if not (is_system_owner or is_own_organization):
            return Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "You don't have permission to update these organization settings"
            }, status=status.HTTP_403_FORBIDDEN)
        
        # O(1) - Single query with select_related, uses index on (organization_id)
        setting = get_object_or_404(
            OrganizationSettings.objects.select_related('organization').only(
                'id', 'organization_id'
            ),
            organization__id=org_id
        )
        
        serializer = OrganizationSettingsSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Settings updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class OrganizationsUnderSystemOwnerAPIView(APIView):
    """
    List and update organizations under a system owner.
    
    Optimized with select_related/prefetch_related for O(1) complexity.
    
    Time Complexity: O(1) for single org, O(n) for list where n = number of orgs
    """
    permission_classes = [IsAuthenticated, IsSystemOwner]

    def get(self, request, org_id=None):
        """
        Get single organization or list all organizations.
        
        Args:
            org_id: Optional organization UUID
            
        Returns:
            Response with organization(s) data
        """
        system_owner = request.user
        
        # If org_id is provided, return single organization
        if org_id:
            # O(1) - Single query with select_related and prefetch_related
            # Uses index on (id, system_owner_id) or primary key
            organization = get_object_or_404(
                OrganizationProfile.objects.select_related(
                    'user', 'system_owner'
                ).prefetch_related(
                    'user__own_organization_profile_setting'
                ).only(
                    'id', 'user_id', 'system_owner_id', 'organization_name',
                    'user__id', 'user__email', 'system_owner__id'
                ),
                id=org_id,
                system_owner=system_owner
            )
            serializer = AllOrganizationProfileSerializer(organization)
            return Response({
                "status": status.HTTP_200_OK,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        # Otherwise return all organizations
        # O(n) - Single query with select_related and prefetch_related
        # Uses index on (system_owner_id)
        organizations = OrganizationProfile.objects.filter(
            system_owner=system_owner
        ).select_related(
            'user', 'system_owner'
        ).prefetch_related(
            'user__own_organization_profile_setting'
        ).only(
            'id', 'user_id', 'system_owner_id', 'organization_name',
            'user__id', 'user__email', 'system_owner__id'
        )
        
        serializer = AllOrganizationProfileSerializer(organizations, many=True)
        return Response({
            "status": status.HTTP_200_OK,
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def put(self, request, org_id):
        """
        Update organization profile.
        
        Args:
            org_id: Organization UUID
            
        Returns:
            Response with updated organization or validation errors
        """
        system_owner = request.user
        
        # O(1) - Single query with select_related, uses index on (id, system_owner_id)
        organization = get_object_or_404(
            OrganizationProfile.objects.select_related('user', 'system_owner').only(
                'id', 'user_id', 'system_owner_id', 'organization_name'
            ),
            id=org_id,
            system_owner=system_owner
        )
        
        serializer = AllOrganizationProfileSerializer(
            organization,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Organization updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class OrganizationLogoUploadAPIView(APIView):
    """
    Upload organization logo file.
    
    Time Complexity: O(1) - Single database query and file write
    """
    permission_classes = [IsAuthenticated, IsSystemOwner]
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    def post(self, request, org_id):
        """
        Upload logo file for organization.
        
        Args:
            org_id: Organization UUID
            
        Returns:
            Response with logo URL or error message
        """
        system_owner = request.user
        
        # O(1) - Single query with select_related, uses index on (id, system_owner_id)
        organization = get_object_or_404(
            OrganizationProfile.objects.select_related('user').only(
                'id', 'user_id', 'system_owner_id'
            ),
            id=org_id,
            system_owner=system_owner
        )
        
        # Check if file is provided
        if 'logo' not in request.FILES:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "No logo file provided"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logo_file = request.FILES['logo']
        
        # Validate file type
        if logo_file.content_type not in self.ALLOWED_IMAGE_TYPES:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": f"Invalid file type. Allowed types: {', '.join(self.ALLOWED_IMAGE_TYPES)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file size
        if logo_file.size > self.MAX_FILE_SIZE:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "File size exceeds 5MB limit"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create organization_logos folder if it doesn't exist
            folder_name = 'organization_logos'
            media_folder = os.path.join(settings.MEDIA_ROOT, folder_name)
            os.makedirs(media_folder, exist_ok=True)
            
            # Generate unique file name
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            file_extension = logo_file.name.split('.')[-1].lower()
            file_name = f"{timestamp}_{unique_id}.{file_extension}"
            file_path = os.path.join(media_folder, file_name)
            
            # Save file
            with open(file_path, 'wb+') as destination:
                for chunk in logo_file.chunks():
                    destination.write(chunk)
            
            # Generate relative path
            relative_path = os.path.join(folder_name, file_name)
            
            # Get or create organization settings - O(1) query
            try:
                org_settings = organization.user.own_organization_profile_setting
            except OrganizationSettings.DoesNotExist:
                org_settings = OrganizationSettings.objects.create(organization=organization.user)
            
            # Update logo - ImageField stores the relative path
            org_settings.organization_logo = relative_path
            org_settings.save(update_fields=['organization_logo'])
            
            # Return full URL path using ImageField's url property
            try:
                logo_url = org_settings.organization_logo.url
            except (ValueError, AttributeError):
                logo_url = f"{settings.MEDIA_URL}{relative_path}"
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Logo uploaded successfully",
                "data": {
                    "logo_path": relative_path,
                    "logo_url": logo_url
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error uploading logo: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SessionInfoAPIView(APIView):
    """
    Get session information for authenticated user.
    
    Optimized with select_related/prefetch_related to avoid N+1 queries.
    
    Time Complexity: O(1) - Single optimized query per role
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get current user's session information based on role.
        
        Returns:
            Response with user data and role-specific information
        """
        user = request.user
        
        # O(1) - Role-based query optimization
        role = user.role
        data = {
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": role,
            "date_joined": user.date_joined,
        }
        
        try:
            if role == "system_owner":
                # O(1) - Single query with select_related, uses index on (user_id) or primary key
                profile = SystemOwnerProfile.objects.select_related('user').filter(
                    user_id=user.id
                ).only('company_name', 'user_id').first()
                
                data["company_name"] = profile.company_name if profile else None
                message = "System Owner authenticated"

            elif role == "organization":
                # O(1) - Single query with select_related and prefetch_related
                # Uses index on (user_id) or primary key
                profile = OrganizationProfile.objects.select_related(
                    'user', 'system_owner'
                ).prefetch_related(
                    'user__own_organization_profile_setting'
                ).filter(user_id=user.id).only(
                    'organization_name', 'system_owner_id', 'user_id'
                ).first()
                
                # O(1) - Single query for settings, uses index on (organization_id)
                settings = OrganizationSettings.objects.filter(
                    organization_id=user.id
                ).only('id', 'organization_id').first() if user else None
                
                data["organization_name"] = profile.organization_name if profile else None
                data["system_owner_id"] = str(profile.system_owner.id) if profile and profile.system_owner else None
                data["settings"] = serialize_org_settings(settings, request=request) if settings else None
                message = "Organization authenticated"

            elif role == "admin":
                # O(1) - Single query with select_related, uses index on (user_id) or primary key
                profile = AdminProfile.objects.select_related(
                    'user', 'organization'
                ).filter(user_id=user.id).only(
                    'admin_name', 'organization_id', 'user_id'
                ).first()
                
                data["admin_name"] = profile.admin_name if profile else None
                data["organization_id"] = str(profile.organization.id) if profile and profile.organization else None
                message = "Admin authenticated"

            elif role == "user":
                # O(1) - Single query with select_related, uses index on (user_id) or primary key
                profile = UserProfile.objects.select_related(
                    'user', 'organization'
                ).filter(user_id=user.id).only(
                    'user_name', 'organization_id', 'user_id', 'is_photo_updated'
                ).first()
                
                data["user_name"] = profile.user_name if profile else None
                data["organization_id"] = str(profile.organization.id) if profile and profile.organization else None
                data["is_photo_updated"] = profile.is_photo_updated if profile else False
                
                # Get current active admin from assignments using utility - O(1) query
                from utils.Employee.assignment_utils import get_current_assignment_for_employee
                current_assignment = get_current_assignment_for_employee(user)
                
                if current_assignment:
                    data["admin_id"] = str(current_assignment.admin.id)
                    data["admin_name"] = current_assignment.admin.own_admin_profile.admin_name if hasattr(current_assignment.admin, 'own_admin_profile') else None
                    data["site_id"] = str(current_assignment.site.id) if current_assignment.site else None
                else:
                    data["admin_id"] = None
                    data["admin_name"] = None
                    data["site_id"] = None
                
                message = "User authenticated"

            else:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Invalid user role"
                }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                "status": status.HTTP_200_OK,
                "message": message,
                "data": data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error fetching session info: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PhotoRefreshToggleAPIView(APIView):
    """
    Toggle is_photo_updated status for an employee.
    When is_photo_updated is False, employee will need to take selfie after login.
    
    Time Complexity: O(1) - Single database update
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        """
        Set is_photo_updated to False for an employee (requires photo update).
        
        Args:
            user_id: Employee UUID
            
        Returns:
            Response with updated is_photo_updated status
        """
        try:
            # O(1) - Single query with select_related, uses index on (user_id) or primary key
            user_profile = get_object_or_404(
                UserProfile.objects.select_related('user').only(
                    'id', 'user_id', 'user__role', 'is_photo_updated'
                ),
                user_id=user_id
            )
            
            # Check if user is an employee
            if user_profile.user.role != 'user':
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Photo update can only be enabled for employees"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set is_photo_updated to False (requires update) - O(1) update
            user_profile.is_photo_updated = False
            user_profile.save(update_fields=['is_photo_updated'])
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Photo update required enabled successfully",
                "data": {
                    "user_id": str(user_profile.user.id),
                    "is_photo_updated": user_profile.is_photo_updated
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error updating photo update status: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, user_id):
        """
        Toggle is_photo_updated status for an employee (True or False).
        
        Args:
            user_id: Employee UUID
            is_photo_updated: Boolean value (True/False) in request.data
            
        Returns:
            Response with updated is_photo_updated status
        """
        try:
            # O(1) - Single query with select_related, uses index on (user_id) or primary key
            user_profile = get_object_or_404(
                UserProfile.objects.select_related('user').only(
                    'id', 'user_id', 'user__role', 'is_photo_updated'
                ),
                user_id=user_id
            )
            
            # Check if user is an employee
            if user_profile.user.role != 'user':
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Photo update can only be toggled for employees"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get is_photo_updated value from request
            is_photo_updated = request.data.get('is_photo_updated')
            if is_photo_updated is None:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "is_photo_updated field is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update is_photo_updated status - O(1) update
            user_profile.is_photo_updated = bool(is_photo_updated)
            user_profile.save(update_fields=['is_photo_updated'])
            
            status_message = "updated" if user_profile.is_photo_updated else "requires update"
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": f"Photo status {status_message} successfully",
                "data": {
                    "user_id": str(user_profile.user.id),
                    "is_photo_updated": user_profile.is_photo_updated
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error updating photo update status: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeProfilePhotoUploadAPIView(APIView):
    """
    Upload employee profile photo from selfie.
    This will also set is_photo_updated to True after successful upload.
    
    Time Complexity: O(1) - Single database update and file write
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        """
        Upload profile photo from base64 selfie image.
        Sets is_photo_updated to True after successful upload.
        
        Args:
            user_id: Employee UUID
            base64_image: Base64 encoded image string (in request.data)
            
        Returns:
            Response with updated profile photo URL and is_photo_updated status
        """
        try:
            from utils.helpers.image_utils import save_base64_image
            
            # O(1) - Single query with select_related, uses index on (user_id) or primary key
            user_profile = get_object_or_404(
                UserProfile.objects.select_related('user').only(
                    'id', 'user_id', 'user__role', 'profile_photo', 'is_photo_updated'
                ),
                user_id=user_id
            )
            
            # Check if user is an employee
            if user_profile.user.role != 'user':
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Profile photo upload is only available for employees"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get base64 image from request
            base64_image = request.data.get("base64_image")
            if not base64_image:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "base64_image is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the image
            try:
                saved_image = save_base64_image(
                    base64_image,
                    folder_name='profile_photos',
                    attendance_type='profile',
                    captured_at=timezone.now()
                )
                
                # Update user profile photo - O(1) update
                user_profile.profile_photo = saved_image.get('file_path', '')
                # Set is_photo_updated to True after successful upload
                user_profile.is_photo_updated = True
                user_profile.save(update_fields=['profile_photo', 'is_photo_updated'])
                
                # Generate full URL for the image
                if user_profile.profile_photo:
                    # Convert ImageFieldFile to string to get the relative path
                    photo_path = str(user_profile.profile_photo)
                    photo_url = request.build_absolute_uri(
                        settings.MEDIA_URL + photo_path
                    )
                else:
                    photo_url = None
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Profile photo updated successfully",
                    "data": {
                        "user_id": str(user_profile.user.id),
                        "profile_photo": photo_url,
                        "is_photo_updated": user_profile.is_photo_updated
                    }
                }, status=status.HTTP_200_OK)
                
            except ValueError as e:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": f"Error processing image: {str(e)}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error uploading profile photo: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

