from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from .models import *
from ServiceShift.models import *
from ServiceWeekOff.models import *
from TaskControl.models import *
from Expenditure.models import * 
from SiteManagement.models import Site
from django.db import transaction

class CustomUserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(required=False)
    password = serializers.CharField(required=False, write_only=True)  # Make password optional for employee auto-generation
    class Meta:
        model = BaseUserModel
        fields = ['id', 'email', 'username', 'password', 'role', 'phone_number']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True},
            'username': {'required': True},
        }

    def validate_phone_number(self, value):
        """Validate phone_number is required and unique for all roles"""
        # For partial updates, if value is not provided, skip validation
        if value is None and self.parent and hasattr(self.parent, 'partial') and self.parent.partial:
            return value
        
        # Convert to integer if string is provided
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise serializers.ValidationError("Phone number is required.")
            try:
                value = int(value)
            except ValueError:
                raise serializers.ValidationError("Phone number must be a valid number.")
        
        if value is None:
            raise serializers.ValidationError("Phone number is required.")
        
        queryset = BaseUserModel.objects.filter(phone_number=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        
        return value

    def validate_email(self, value):
        """Validate email is unique"""
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required.")
        value = value.strip()
        
        queryset = BaseUserModel.objects.filter(email=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        
        return value

    def validate_username(self, value):
        """Validate username is unique"""
        if not value or not value.strip():
            raise serializers.ValidationError("Username is required.")
        value = value.strip()
        
        queryset = BaseUserModel.objects.filter(username=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("A user with this username already exists.")
        
        return value

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])  # Hash password
        return BaseUserModel.objects.create(**validated_data)


# ==================== REGISTRATION SERIALIZERS (Only for Registration) ====================

# System Owner Profile Serializer - ONLY FOR REGISTRATION
class SystemOwnerProfileSerializer(serializers.ModelSerializer):
    """
    Registration serializer for System Owner.
    This serializer should ONLY be used in registration endpoints.
    """
    user = CustomUserSerializer()

    class Meta:
        model = SystemOwnerProfile
        fields = ['id', 'user', 'company_name']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'system_owner'
        user = BaseUserModel.objects.create_user(**user_data)
        return SystemOwnerProfile.objects.create(user=user, **validated_data)


# Organization Profile Serializer - ONLY FOR REGISTRATION
class OrganizationProfileSerializer(serializers.ModelSerializer):
    """
    Registration serializer for Organization.
    This serializer should ONLY be used in registration endpoints.
    """
    user = CustomUserSerializer()
    system_owner = serializers.PrimaryKeyRelatedField(queryset=BaseUserModel.objects.all())

    state = serializers.CharField(required=True, max_length=100)
    city = serializers.CharField(required=True, max_length=100)
    
    class Meta:
        model = OrganizationProfile
        fields = ['id', 'user', 'organization_name', 'system_owner', 'state', 'city']
    
    def validate_organization_name(self, value):
        """Validate that organization_name is unique"""
        if not value or not value.strip():
            raise serializers.ValidationError("Organization name is required.")
        
        value = value.strip()
        
        # Check if this is an update (instance exists) or create (no instance)
        if self.instance:
            # For update, check if another organization has this name
            if OrganizationProfile.objects.filter(organization_name__iexact=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("An organization with this name already exists.")
        else:
            # For create, check if any organization has this name
            if OrganizationProfile.objects.filter(organization_name__iexact=value).exists():
                raise serializers.ValidationError("An organization with this name already exists.")
        
        return value
    
    def validate_state(self, value):
        """Validate that state is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("State is required.")
        return value.strip()
    
    def validate_city(self, value):
        """Validate that city is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("City is required.")
        return value.strip()

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'organization'
        base_user = BaseUserModel.objects.create_user(**user_data)  # ✅ Create user

        # ✅ Create settings linked to this user
        OrganizationSettings.objects.create(organization=base_user)

        # ✅ Create and return the OrganizationProfile
        return OrganizationProfile.objects.create(user=base_user, **validated_data)
        
    


# Admin Profile Serializer - ONLY FOR REGISTRATION
class AdminProfileSerializer(serializers.ModelSerializer):
    """
    Registration serializer for Admin.
    This serializer should ONLY be used in registration endpoints.
    """
    user = CustomUserSerializer()
    organization = serializers.PrimaryKeyRelatedField(queryset=BaseUserModel.objects.all())
    
    state = serializers.CharField(required=True, max_length=100)
    city = serializers.CharField(required=True, max_length=100)
    
    class Meta:
        model = AdminProfile
        fields = ['id', 'user', 'admin_name', 'organization', 'state', 'city']
    
    def validate_admin_name(self, value):
        """Validate that admin_name is unique"""
        if not value or not value.strip():
            raise serializers.ValidationError("Admin name is required.")
        
        value = value.strip()
        
        # For registration (no instance), check if any admin has this name
        if AdminProfile.objects.filter(admin_name__iexact=value).exists():
            raise serializers.ValidationError("An admin with this name already exists.")
        
        return value
    
    def validate_state(self, value):
        """Validate that state is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("State is required.")
        return value.strip()
    
    def validate_city(self, value):
        """Validate that city is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("City is required.")
        return value.strip()

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'admin'
        user = BaseUserModel.objects.create_user(**user_data)
        admin_profile = AdminProfile.objects.create(user=user, **validated_data)
        
        # Create default site for admin
        organization = admin_profile.organization
        default_site_name = f"{admin_profile.admin_name}'s Site"
        # Get address, city, state from validated_data or use defaults
        address = validated_data.get('address', '')
        city = validated_data.get('city', '')
        state = validated_data.get('state', '')
        
        # If address is empty, provide a default address
        if not address:
            address = f"{city}, {state}" if city and state else "Address not provided"
        
        default_site = Site.objects.create(
            organization=organization,
            created_by_admin=user,
            site_name=default_site_name,
            address=address,
            city=city if city else 'Not specified',
            state=state if state else 'Not specified',
            is_active=True
        )
        
        # Create default resources for the site
        from SiteManagement.utils import create_default_site_resources
        create_default_site_resources(admin=user, site=default_site)
        
        return admin_profile


# User Profile Serializer - ONLY FOR REGISTRATION
class UserProfileSerializer(serializers.ModelSerializer):
    """
    Registration serializer for Employee/User.
    This serializer should ONLY be used in registration endpoints.
    """
    user = CustomUserSerializer()
    organization = serializers.PrimaryKeyRelatedField(
        queryset=BaseUserModel.objects.filter(role='organization'),
        required=False,
        allow_null=True,
        write_only=False
    )
    custom_employee_id = serializers.CharField(required=True, max_length=255)
    state = serializers.CharField(required=True, max_length=100)
    city = serializers.CharField(required=True, max_length=100)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = "__all__"
        read_only_fields = ['id', 'is_active']
    
    def get_is_active(self, obj):
        """Return user is_active status"""
        return obj.user.is_active if obj.user else None
    
    def validate(self, attrs):
        """Validate that phone_number, date_of_joining, and gender are provided for user role"""
        # For updates (partial=True), only validate fields that are being updated
        is_update = self.instance is not None
        
        # For create (not update), validate required fields
        if not is_update:
            user_data = attrs.get('user', {})
            phone_number = user_data.get('phone_number') if user_data else None
            date_of_joining = attrs.get('date_of_joining')
            gender = attrs.get('gender')
            
            # For create, phone_number is required
            if phone_number is None:
                raise serializers.ValidationError({
                    'user': {
                        'phone_number': 'Phone number is required.'
                    }
                })
            # Convert to integer if string is provided
            if isinstance(phone_number, str):
                phone_number = phone_number.strip()
                if not phone_number:
                    raise serializers.ValidationError({
                        'user': {
                            'phone_number': 'Phone number is required.'
                        }
                    })
                try:
                    phone_number = int(phone_number)
                    attrs['user']['phone_number'] = phone_number
                except ValueError:
                    raise serializers.ValidationError({
                        'user': {
                            'phone_number': 'Phone number must be a valid number.'
                        }
                    })
            
            # For create, date_of_joining is required
            if not date_of_joining:
                raise serializers.ValidationError({
                    'date_of_joining': 'Date of joining is required for user role.'
                })
            
            # For create, gender is required
            if not gender or not gender.strip():
                raise serializers.ValidationError({
                    'gender': 'Gender is required for user role.'
                })
            
            # For create, state is required
            state = attrs.get('state')
            if not state or not state.strip():
                raise serializers.ValidationError({
                    'state': 'State is required for user role.'
                })
            
            # For create, city is required
            city = attrs.get('city')
            if not city or not city.strip():
                raise serializers.ValidationError({
                    'city': 'City is required for user role.'
                })
        
        # For updates, only validate fields that are being provided
        if is_update:
            # Only validate phone_number if it's being provided in user_data
            if 'user' in attrs and attrs['user']:
                user_data = attrs.get('user', {})
                phone_number = user_data.get('phone_number') if user_data else None
                if phone_number is not None:
                    # Convert to integer if string is provided
                    if isinstance(phone_number, str):
                        phone_number = phone_number.strip()
                        if not phone_number:
                            raise serializers.ValidationError({
                                'user': {
                                    'phone_number': 'Phone number cannot be empty.'
                                }
                            })
                        try:
                            phone_number = int(phone_number)
                            user_data['phone_number'] = phone_number
                        except ValueError:
                            raise serializers.ValidationError({
                                'user': {
                                    'phone_number': 'Phone number must be a valid number.'
                                }
                            })
        
        return attrs
    
    def validate_custom_employee_id(self, value):
        """Validate that custom_employee_id is unique and remove spaces"""
        if not value or not value.strip():
            raise serializers.ValidationError("custom_employee_id is required and cannot be empty.")
        
        # Remove spaces from custom_employee_id
        value = value.strip().replace(' ', '')
        
        # Check if this is an update (instance exists) or create (no instance)
        if self.instance:
            # For update, check if another user has this ID
            if UserProfile.objects.filter(custom_employee_id=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("This custom_employee_id is already taken.")
        else:
            # For create, check if any user has this ID
            if UserProfile.objects.filter(custom_employee_id=value).exists():
                raise serializers.ValidationError("This custom_employee_id is already taken.")
        
        return value
    
    def validate_state(self, value):
        """Validate that state is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("State is required.")
        return value.strip()
    
    def validate_city(self, value):
        """Validate that city is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("City is required.")
        return value.strip()

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'user'
        
        # Ensure phone_number is provided for user role
        phone_number = user_data.get('phone_number')
        if not phone_number:
            raise serializers.ValidationError({"user": {"phone_number": "Phone number is required for user role."}})
        
        # Convert to integer if string is provided
        if isinstance(phone_number, str):
            phone_number = phone_number.strip()
            if not phone_number:
                raise serializers.ValidationError({"user": {"phone_number": "Phone number is required for user role."}})
            try:
                user_data['phone_number'] = int(phone_number)
            except ValueError:
                raise serializers.ValidationError({"user": {"phone_number": "Phone number must be a valid number."}})
        
        # For employees, always auto-generate password as custom_employee_id@123
        custom_emp_id = validated_data.get('custom_employee_id', '')
        if not custom_emp_id:
            raise serializers.ValidationError({"custom_employee_id": "custom_employee_id is required for employee registration."})
        
        # Auto-generate password for employees (ignore any password provided in user_data)
        auto_password = f"{custom_emp_id}@123"
        user_data['password'] = auto_password
        
        user = BaseUserModel.objects.create_user(**user_data)

        # Get admin - it should be provided by view logic or in request
        admin_user = None
        request = self.context.get('request')
        if request and request.user and request.user.role == 'admin':
            admin_user = request.user
        else:
            raise serializers.ValidationError({"admin": ["Admin context is required for employee registration."]})
        
        try:
            admin_profile = AdminProfile.objects.get(user=admin_user)
        except AdminProfile.DoesNotExist:
            raise serializers.ValidationError({"admin": ["Selected admin has no AdminProfile"]})

        # Set organization from admin (override if provided in request)
        validated_data['organization'] = admin_profile.organization
        
        # Set admin FK for backward compatibility
        validated_data['admin'] = admin_user

        # Ensure custom_employee_id is provided
        if 'custom_employee_id' not in validated_data or not validated_data['custom_employee_id']:
            raise serializers.ValidationError({"custom_employee_id": "This field is required."})
        
        # Ensure state is provided
        if 'state' not in validated_data or not validated_data.get('state'):
            raise serializers.ValidationError({"state": "This field is required."})
        
        # Ensure city is provided
        if 'city' not in validated_data or not validated_data.get('city'):
            raise serializers.ValidationError({"city": "This field is required."})

        # Create profile first
        profile = UserProfile.objects.create(user=user, **validated_data)

        # Assign defaults (M2M fields)
        shift_ids = ServiceShift.objects.filter(admin=admin_user, is_active=True).values_list('id', flat=True)[:1]
        week_off_ids = WeekOffPolicy.objects.filter(admin=admin_user).values_list('id', flat=True)[:1]
        location_ids = Location.objects.filter(admin=admin_user, is_active=True).values_list('id', flat=True)[:1]

        profile.shifts.set(shift_ids)
        profile.week_offs.set(week_off_ids)
        profile.locations.set(location_ids)

        # Create initial assignment record
        from SiteManagement.models import EmployeeAdminSiteAssignment, Site
        
        # Get site_id from context (passed from view) or use default
        request = self.context.get('request')
        site_id = self.context.get('site_id')
        
        selected_site = None
        
        # If site_id is provided in payload, use that site
        if site_id:
            try:
                selected_site = Site.objects.filter(
                    id=site_id,
                    created_by_admin=admin_user,
                    is_active=True
                ).first()
                
                if not selected_site:
                    raise serializers.ValidationError({
                        "site_id": [f"Site with id {site_id} not found or does not belong to this admin."]
                    })
            except Exception as e:
                raise serializers.ValidationError({
                    "site_id": [f"Invalid site_id: {str(e)}"]
                })
        else:
            # Get admin's default site (first created active site by this admin)
            selected_site = Site.objects.filter(
                created_by_admin=admin_user,
                is_active=True
            ).order_by('created_at').first()
        
        # Create assignment with selected site (from payload) or default site
        EmployeeAdminSiteAssignment.objects.create(
            employee=user,
            admin=admin_user,
            site=selected_site,  # Use site from payload or default site
            start_date=validated_data.get('date_of_joining', timezone.now().date()),
            end_date=None,  # Active assignment
            is_active=True,
            assigned_by=admin_user,
            assignment_reason='Initial assignment during registration'
        )

        return profile


# ==================== READ/UPDATE SERIALIZERS (For Listing and Updating) ====================

class AdminProfileReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for Admin Profile.
    Used for listing and retrieving admin data (NOT for registration).
    """
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminProfile
        fields = ['id', 'user_id', 'admin_name', 'organization', 'email', 'username', 'phone_number', 'status', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user_id', 'organization', 'created_at', 'updated_at']
    
    def get_email(self, obj):
        """Return admin user email"""
        return obj.user.email if obj.user else None
    
    def get_username(self, obj):
        """Return admin user username"""
        return obj.user.username if obj.user else None
    
    def get_phone_number(self, obj):
        """Return admin user phone number"""
        return obj.user.phone_number if obj.user else None
    
    def get_status(self, obj):
        """Return admin user status (is_active)"""
        return obj.user.is_active if obj.user else None
    
    def get_is_active(self, obj):
        """Return admin user is_active directly"""
        return obj.user.is_active if obj.user else None
    
    def get_user_id(self, obj):
        """Return admin user ID (UID)"""
        return str(obj.user.id) if obj.user else None


class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Update serializer for Admin Profile.
    Used for updating admin data (NOT for registration).
    """
    email = serializers.EmailField(required=False, allow_blank=False)
    username = serializers.CharField(required=False, max_length=150)
    phone_number = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = AdminProfile
        fields = ['admin_name', 'email', 'username', 'phone_number', 'is_active']
    
    def validate_admin_name(self, value):
        """Validate that admin_name is unique"""
        if value and value.strip():
            value = value.strip()
            # For update, check if another admin has this name
            if self.instance:
                if AdminProfile.objects.filter(admin_name__iexact=value).exclude(id=self.instance.id).exists():
                    raise serializers.ValidationError("An admin with this name already exists.")
            return value
        return value
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if value and value.strip():
            value = value.strip()
            if self.instance and self.instance.user:
                if BaseUserModel.objects.filter(email=value).exclude(id=self.instance.user.id).exists():
                    raise serializers.ValidationError("A user with this email already exists.")
            return value
        return value
    
    def validate_username(self, value):
        """Validate username uniqueness"""
        if value and value.strip():
            value = value.strip()
            if self.instance and self.instance.user:
                if BaseUserModel.objects.filter(username=value).exclude(id=self.instance.user.id).exists():
                    raise serializers.ValidationError("A user with this username already exists.")
            return value
        return value
    
    def validate_phone_number(self, value):
        """Validate phone_number uniqueness"""
        if value is not None:
            # Convert to integer if string is provided
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return value
                try:
                    value = int(value)
                except ValueError:
                    raise serializers.ValidationError("Phone number must be a valid number.")
            
            if self.instance and self.instance.user:
                if BaseUserModel.objects.filter(phone_number=value).exclude(id=self.instance.user.id).exists():
                    raise serializers.ValidationError("A user with this phone number already exists.")
            return value
        return value
    
    def update(self, instance, validated_data):
        """Update admin profile and user details"""
        # Update admin_name if provided
        if 'admin_name' in validated_data:
            instance.admin_name = validated_data.pop('admin_name')
        
        # Update user fields if provided
        user = instance.user
        if user:
            if 'email' in validated_data:
                user.email = validated_data.pop('email')
            if 'username' in validated_data:
                user.username = validated_data.pop('username')
            if 'phone_number' in validated_data:
                user.phone_number = validated_data.pop('phone_number')
            if 'is_active' in validated_data:
                user.is_active = validated_data.pop('is_active')
            user.save()
        
        instance.save()
        return instance


class UserProfileReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for User/Employee Profile.
    Used for listing and retrieving employee data (NOT for registration).
    """
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = "__all__"
        read_only_fields = ['id', 'user', 'organization']
    
    def get_email(self, obj):
        """Return user email"""
        return obj.user.email if obj.user else None
    
    def get_username(self, obj):
        """Return user username"""
        return obj.user.username if obj.user else None
    
    def get_phone_number(self, obj):
        """Return user phone number"""
        return obj.user.phone_number if obj.user else None
    
    def get_is_active(self, obj):
        """Return user is_active status"""
        return obj.user.is_active if obj.user else None
    
    def get_profile_photo_url(self, obj):
        """Return full URL for profile photo"""
        if obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
            return obj.profile_photo.url
        return None
    
    def get_user_id(self, obj):
        """Return user ID (UID)"""
        return str(obj.user.id) if obj.user else None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Update serializer for User/Employee Profile.
    Used for updating employee data (NOT for registration).
    """
    email = serializers.EmailField(required=False, allow_blank=False)
    username = serializers.CharField(required=False, max_length=150)
    phone_number = serializers.IntegerField(required=False)
    custom_employee_id = serializers.CharField(required=False, max_length=255)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = UserProfile
        fields = [
            'user_name', 'custom_employee_id', 'email', 'username', 'phone_number',
            'date_of_birth', 'date_of_joining', 'gender', 'designation', 'job_title',
            'is_active'
        ]
    
    def validate_custom_employee_id(self, value):
        """Validate that custom_employee_id is unique"""
        if value and value.strip():
            value = value.strip()
            # For update, check if another user has this ID
            if self.instance:
                if UserProfile.objects.filter(custom_employee_id=value).exclude(id=self.instance.id).exists():
                    raise serializers.ValidationError("This custom_employee_id is already taken.")
            return value
        return value
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if value and value.strip():
            value = value.strip()
            if self.instance and self.instance.user:
                if BaseUserModel.objects.filter(email=value).exclude(id=self.instance.user.id).exists():
                    raise serializers.ValidationError("A user with this email already exists.")
            return value
        return value
    
    def validate_username(self, value):
        """Validate username uniqueness"""
        if value and value.strip():
            value = value.strip()
            if self.instance and self.instance.user:
                if BaseUserModel.objects.filter(username=value).exclude(id=self.instance.user.id).exists():
                    raise serializers.ValidationError("A user with this username already exists.")
            return value
        return value
    
    def validate_phone_number(self, value):
        """Validate phone_number uniqueness"""
        if value is not None:
            # Convert to integer if string is provided
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return value
                try:
                    value = int(value)
                except ValueError:
                    raise serializers.ValidationError("Phone number must be a valid number.")
            
            if self.instance and self.instance.user:
                if BaseUserModel.objects.filter(phone_number=value).exclude(id=self.instance.user.id).exists():
                    raise serializers.ValidationError("A user with this phone number already exists.")
            return value
        return value
    
    def update(self, instance, validated_data):
        """Update user profile and user details"""
        # Update profile fields
        profile_fields = ['user_name', 'custom_employee_id', 'date_of_birth', 'date_of_joining', 
                         'gender', 'designation', 'job_title']
        for field in profile_fields:
            if field in validated_data:
                setattr(instance, field, validated_data.pop(field))
        
        # Update user fields if provided
        user = instance.user
        if user:
            if 'email' in validated_data:
                user.email = validated_data.pop('email')
            if 'username' in validated_data:
                user.username = validated_data.pop('username')
            if 'phone_number' in validated_data:
                user.phone_number = validated_data.pop('phone_number')
            if 'is_active' in validated_data:
                user.is_active = validated_data.pop('is_active')
            user.save()
        
        instance.save()
        return instance


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    organization_logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = OrganizationSettings
        fields = '__all__'
    
    def validate_enabled_menu_items(self, value):
        """
        Validate enabled_menu_items field.
        Supports both legacy format (boolean) and new role-based format (object).
        Format examples:
        - Legacy: {"menu_base": true} or {"menu_base": false}
        - New: {"menu_base": {"admin": true, "organization": false}}
        """
        if value is None:
            return {}
        
        # Handle string input (from form data or JSON string)
        if isinstance(value, str):
            try:
                import json
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("enabled_menu_items must be a dictionary")
        
        validated_value = {}
        for key, item_value in value.items():
            # Validate key is a string (convert if needed)
            if not isinstance(key, str):
                try:
                    key = str(key)
                except (TypeError, ValueError):
                    continue
            
            # Handle legacy boolean format
            if isinstance(item_value, bool):
                validated_value[key] = item_value
            # Handle string booleans (from form data)
            elif isinstance(item_value, str):
                item_lower = item_value.lower().strip()
                if item_lower in ('true', '1', 'yes', 'on'):
                    validated_value[key] = True
                elif item_lower in ('false', '0', 'no', 'off', ''):
                    validated_value[key] = False
                # If it's a JSON string, try to parse it
                elif item_value.startswith('{') and item_value.endswith('}'):
                    try:
                        import json
                        parsed = json.loads(item_value)
                        if isinstance(parsed, dict):
                            item_value = parsed
                        else:
                            continue
                    except (json.JSONDecodeError, TypeError):
                        continue
                else:
                    continue
            # Handle new role-based format
            elif isinstance(item_value, dict):
                role_based = {}
                if 'admin' in item_value:
                    admin_val = item_value['admin']
                    # Handle boolean
                    if isinstance(admin_val, bool):
                        role_based['admin'] = admin_val
                    # Handle string boolean
                    elif isinstance(admin_val, str):
                        admin_lower = admin_val.lower().strip()
                        if admin_lower in ('true', '1', 'yes', 'on'):
                            role_based['admin'] = True
                        elif admin_lower in ('false', '0', 'no', 'off', ''):
                            role_based['admin'] = False
                
                if 'organization' in item_value:
                    org_val = item_value['organization']
                    # Handle boolean
                    if isinstance(org_val, bool):
                        role_based['organization'] = org_val
                    # Handle string boolean
                    elif isinstance(org_val, str):
                        org_lower = org_val.lower().strip()
                        if org_lower in ('true', '1', 'yes', 'on'):
                            role_based['organization'] = True
                        elif org_lower in ('false', '0', 'no', 'off', ''):
                            role_based['organization'] = False
                
                # Only add if at least one role is set
                if role_based:
                    validated_value[key] = role_based
            # Skip invalid values (not bool, str, or dict)
            else:
                continue
        
        return validated_value
    
    def get_organization_logo_url(self, obj):
        """Return full URL for organization logo"""
        if obj.organization_logo:
            # ImageField provides .url property for full URL
            try:
                return obj.organization_logo.url
            except (ValueError, AttributeError):
                # Fallback for string paths or when file doesn't exist
                from django.conf import settings
                if str(obj.organization_logo).startswith('http'):
                    return str(obj.organization_logo)
                return f"{settings.MEDIA_URL}{obj.organization_logo}"
        return None


class AllOrganizationProfileSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()  # Read-only for representation
    system_owner = serializers.PrimaryKeyRelatedField(read_only=True)
    is_user_active = serializers.SerializerMethodField()  # 👈 custom field
    organization_settings = serializers.SerializerMethodField()  # Settings as nested object
    organization_logo = serializers.SerializerMethodField()  # Logo URL for easy access

    class Meta:
        model = OrganizationProfile
        fields = ['id', 'user', 'organization_name', 'system_owner', 'created_at', 'updated_at', 'is_user_active', 'organization_settings', 'organization_logo']
        read_only_fields = ['id', 'system_owner', 'created_at', 'user']

    def get_is_user_active(self, obj):
        return obj.user.is_active

    def get_user(self, obj):
        """Return user data using CustomUserSerializer"""
        if obj and obj.user:
            user_serializer = CustomUserSerializer(obj.user)
            return user_serializer.data
        return None

    def get_organization_settings(self, obj):
        """Return organization settings using OrganizationSettingsSerializer"""
        try:
            settings = obj.user.own_organization_profile_setting
            settings_serializer = OrganizationSettingsSerializer(settings)
            return settings_serializer.data
        except OrganizationSettings.DoesNotExist:
            return None
    
    def get_organization_logo(self, obj):
        """Return organization logo URL"""
        try:
            settings = obj.user.own_organization_profile_setting
            if settings and settings.organization_logo:
                # ImageField provides .url property for full URL
                try:
                    return settings.organization_logo.url
                except (ValueError, AttributeError):
                    # Fallback for string paths or when file doesn't exist
                    from django.conf import settings as django_settings
                    if str(settings.organization_logo).startswith('http'):
                        return str(settings.organization_logo)
                    return f"{django_settings.MEDIA_URL}{settings.organization_logo}"
            return None
        except OrganizationSettings.DoesNotExist:
            return None

    def update(self, instance, validated_data):
        """Update organization profile and user details"""
        # Get user data from initial_data (raw request data) to avoid DictField conversion issues
        user_data = {}
        if hasattr(self, 'initial_data') and 'user' in self.initial_data:
            raw_user_data = self.initial_data.get('user')
            if isinstance(raw_user_data, dict):
                user_data = raw_user_data
            elif raw_user_data is None:
                user_data = {}
        else:
            # Fallback to validated_data if initial_data not available
            user_data_raw = validated_data.pop('user', None)
            if isinstance(user_data_raw, dict):
                user_data = user_data_raw
        
        # Update organization profile fields
        if 'organization_name' in validated_data:
            new_org_name = validated_data['organization_name'].strip() if validated_data['organization_name'] else None
            if new_org_name and new_org_name != instance.organization_name:
                # Check uniqueness excluding current organization
                if OrganizationProfile.objects.filter(organization_name__iexact=new_org_name).exclude(id=instance.id).exists():
                    raise serializers.ValidationError({
                        'organization_name': ['An organization with this name already exists.']
                    })
            instance.organization_name = new_org_name
        
        # Update user fields if provided
        user = instance.user
        if user_data and isinstance(user_data, dict):
            # Validate and update email if changed
            if 'email' in user_data:
                email = user_data['email'].strip() if user_data['email'] and isinstance(user_data['email'], str) else (str(user_data['email']) if user_data['email'] else None)
                if email:
                    if email != user.email:
                        # Check uniqueness excluding current user
                        if BaseUserModel.objects.filter(email=email).exclude(id=user.id).exists():
                            raise serializers.ValidationError({
                                'user': {'email': ['A user with this email already exists.']}
                            })
                        user.email = email
            
            # Validate and update username if changed
            if 'username' in user_data:
                username = user_data['username'].strip() if user_data['username'] and isinstance(user_data['username'], str) else (str(user_data['username']) if user_data['username'] else None)
                if username:
                    if username != user.username:
                        # Check uniqueness excluding current user
                        if BaseUserModel.objects.filter(username=username).exclude(id=user.id).exists():
                            raise serializers.ValidationError({
                                'user': {'username': ['A user with this username already exists.']}
                            })
                        user.username = username
            
            # Validate and update phone_number if changed
            if 'phone_number' in user_data:
                phone_number_value = user_data['phone_number']
                if phone_number_value is None:
                    phone_number = None
                elif isinstance(phone_number_value, str):
                    phone_number = phone_number_value.strip()
                else:
                    # If it's already an integer, use it directly
                    phone_number = phone_number_value
                if phone_number:
                    if phone_number != user.phone_number:
                        # Check uniqueness excluding current user
                        if BaseUserModel.objects.filter(phone_number=phone_number).exclude(id=user.id).exists():
                            raise serializers.ValidationError({
                                'user': {'phone_number': ['A user with this phone number already exists.']}
                            })
                        user.phone_number = phone_number
            
            # Update is_active if provided
            if 'is_active' in user_data:
                user.is_active = user_data['is_active']
            
            # Update password if provided
            if 'password' in user_data and user_data['password']:
                user.set_password(user_data['password'])
            
            user.save()
        
        # Update organization settings if provided
        settings_data = {}
        if hasattr(self, 'initial_data') and 'organization_settings' in self.initial_data:
            raw_settings_data = self.initial_data.get('organization_settings')
            if isinstance(raw_settings_data, dict):
                settings_data = raw_settings_data
        
        if settings_data and isinstance(settings_data, dict):
            # Get or create organization settings
            try:
                org_settings = instance.user.own_organization_profile_setting
            except OrganizationSettings.DoesNotExist:
                # Create settings if they don't exist
                org_settings = OrganizationSettings.objects.create(organization=instance.user)
            
            # Ensure auto_checkout and auto_shiftwise_checkout are mutually exclusive
            if 'auto_checkout_enabled' in settings_data and settings_data.get('auto_checkout_enabled'):
                settings_data['auto_shiftwise_checkout_enabled'] = False
            elif 'auto_shiftwise_checkout_enabled' in settings_data and settings_data.get('auto_shiftwise_checkout_enabled'):
                settings_data['auto_checkout_enabled'] = False
            
            # Update settings fields
            settings_serializer = OrganizationSettingsSerializer(
                org_settings, 
                data=settings_data, 
                partial=True
            )
            if settings_serializer.is_valid():
                settings_serializer.save()
            else:
                raise serializers.ValidationError({
                    'organization_settings': settings_serializer.errors
                })
        
        instance.save()
        return instance


# ==================== ADDITIONAL UTILITY SERIALIZERS ====================

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change operation.
    
    Fields:
        - old_password (str, optional): Current password (required unless force_change=True)
        - new_password (str, required): New password (min 8 characters)
        - force_change (bool, optional): Force password change without old password
    """
    old_password = serializers.CharField(required=False, write_only=True, allow_blank=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    force_change = serializers.BooleanField(required=False, default=False)
    
    def validate_new_password(self, value):
        """Validate new password strength."""
        if not value or len(value.strip()) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value.strip()
    
    def validate(self, attrs):
        """Cross-field validation."""
        force_change = attrs.get('force_change', False)
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        
        # If not force change, old_password is required
        if not force_change and not old_password:
            raise serializers.ValidationError({
                'old_password': 'Old password is required when force_change is False.'
            })
        
        return attrs


class EmployeeActivateSerializer(serializers.Serializer):
    """
    Serializer for employee activation/deactivation.
    
    Fields:
        - action (str, required): 'activate' or 'deactivate'
    """
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate'],
        default='deactivate'
    )


class EmployeeTransferSerializer(serializers.Serializer):
    """
    Serializer for transferring employees to another admin.
    
    Fields:
        - employee_ids (list, required): List of employee UUIDs
        - new_admin_id (UUID, required): Target admin UUID
    """
    employee_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1
    )
    new_admin_id = serializers.UUIDField(required=True)
    
    def validate_employee_ids(self, value):
        """Validate employee_ids list."""
        if not value or len(value) == 0:
            raise serializers.ValidationError("employee_ids list cannot be empty.")
        return value


class EmployeeStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating employee status for a specific date.
    
    Fields:
        - employee_ids (list, required): List of employee UUIDs
        - status (str, required): 'active' or 'inactive'
    """
    employee_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1
    )
    status = serializers.ChoiceField(
        choices=['active', 'inactive'],
        required=True
    )


class GeoFencingUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating geo-fencing settings.
    
    Fields:
        - allow_geo_fencing (bool, optional): Enable/disable geo-fencing
        - radius (int, optional): Radius in meters (positive integer)
    """
    allow_geo_fencing = serializers.BooleanField(required=False, default=False)
    radius = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    
    def validate_radius(self, value):
        """Validate radius if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError("Radius must be a positive integer.")
        return value


class BulkActivateDeactivateSerializer(serializers.Serializer):
    """
    Serializer for bulk activate/deactivate operations.
    
    Fields:
        - employee_ids (list, required): List of employee UUIDs
        - action (str, required): 'activate' or 'deactivate'
    """
    employee_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1
    )
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate'],
        required=True
    )


class FcmTokenUpdateSerializer(serializers.Serializer):
    """
    Serializer for FCM token update.
    
    Fields:
        - fcm_token (str, required): Firebase Cloud Messaging token
    """
    fcm_token = serializers.CharField(required=True, max_length=255)
    
    def validate_fcm_token(self, value):
        """Validate FCM token."""
        if not value:
            raise serializers.ValidationError("FCM token cannot be empty.")
        value = value.strip()
        if not value:
            raise serializers.ValidationError("FCM token cannot be empty.")
        return value