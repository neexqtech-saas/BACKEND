import uuid
from django.db import models

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.utils.timezone import now

# ---------------------------
# ✅ Custom User Manager
# ---------------------------
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


# ---------------------------
# ✅ Custom User Model
# ---------------------------
class BaseUserModel(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("system_owner", "System Owner"),
        ("organization", "Organization"),
        ("admin", "Admin"),
        ("user", "User"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, blank=False, null=False)
    username = models.CharField(max_length=150, unique=True, blank=False, null=False)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    phone_number = models.BigIntegerField(blank=False, null=False, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(Group, related_name="customuser_groups", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="customuser_permissions", blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        indexes = [
            # Role-based queries optimization
            models.Index(fields=['role', 'is_active'], name='user_role_active_idx'),
            # Login optimization - email and username already have unique constraints
            models.Index(fields=['email'], name='user_email_idx'),
            models.Index(fields=['username'], name='user_username_idx'),
        ]

    def __str__(self):
        return self.email


class SystemOwnerProfile(models.Model): 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # (IGNORE NOT IN USED)
    user = models.OneToOneField(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'system_owner'},related_name='own_system_owner_profile')
    company_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            # User lookup optimization - OneToOne already creates index, but explicit for clarity
            models.Index(fields=['user'], name='so_user_idx'),
        ]


class OrganizationProfile(models.Model): 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # (IGNORE NOT IN USED)
    user = models.OneToOneField(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'organization'},  related_name='own_organization_profile')  # 👈 Unique reverse accessor)
    organization_name = models.CharField(max_length=255)
    system_owner = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'system_owner'}, related_name='under_syster_owner')
    state = models.CharField(max_length=100, blank=False, null=False)
    city = models.CharField(max_length=100, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            # User lookup optimization - OneToOne already creates index
            models.Index(fields=['user'], name='org_user_idx'),
            # System owner filtering - O(1) queries
            models.Index(fields=['system_owner'], name='org_system_owner_idx'),
            # Composite index for system owner queries
            models.Index(fields=['system_owner', 'id'], name='org_system_owner_id_idx'),
        ]

 
class AdminProfile(models.Model): 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # (IGNORE NOT IN USED)
    user = models.OneToOneField(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'admin'},related_name='own_admin_profile')
    admin_name = models.CharField(max_length=255)
    organization = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'organization'},related_name='under_organization_profile')
    state = models.CharField(max_length=100, blank=False, null=False)
    city = models.CharField(max_length=100, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            # User lookup optimization - OneToOne already creates index
            models.Index(fields=['user'], name='admin_user_idx'),
            # Organization filtering - O(1) queries
            models.Index(fields=['organization'], name='admin_organization_idx'),
            # Composite index for organization admin validation - O(1) queries
            models.Index(fields=['user', 'organization'], name='admin_user_org_idx'),
        ]

from ServiceShift.models import *
from ServiceWeekOff.models import *
from LocationControl.models import *

class UserProfile(models.Model):
    TYPE_CHOICES = [
        ("employee", "Employee"),
        ("supervisor", "Supervisor"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # (IGNORE NOT IN USED)
    user = models.OneToOneField(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'user'},related_name='own_user_profile')
    user_name = models.CharField(max_length=255)
    organization = models.ForeignKey(BaseUserModel, on_delete=models.CASCADE, limit_choices_to={'role': 'organization'},related_name='under_organization_profile_user')
    admin = models.ForeignKey(BaseUserModel, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'role': 'admin'}, related_name='under_admin_profile', help_text="Primary admin for this employee (legacy field, use EmployeeAdminSiteAssignment for multi-admin support)")
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True, help_text="User profile photo")
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=20, blank=False, null=False)
    blood_group = models.CharField(max_length=10, blank=True)
    date_of_joining = models.DateField(null=False, blank=False)
    allow_geo_fencing = models.BooleanField(default=False)
    job_title = models.CharField(max_length=255, blank=True)
    fcm_token = models.CharField(max_length=255, blank=True)
    radius = models.IntegerField(null=True, blank=True)
    shifts = models.ManyToManyField(ServiceShift, blank=True, related_name='users_shifts')
    week_offs = models.ManyToManyField(WeekOffPolicy, blank=True, related_name='users_week_off')
    locations = models.ManyToManyField(Location, blank=True, related_name='users_location')
    custom_employee_id = models.CharField(max_length=255, blank=False, null=False, unique=True)
    referral_contact_number = models.CharField(max_length=20, blank=True)
    emergency_contact_no = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    user_type = models.CharField(max_length=100,choices=TYPE_CHOICES,default="employee")
    state = models.CharField(max_length=100, blank=False, null=False)
    city = models.CharField(max_length=100, blank=False, null=False)
    is_photo_updated = models.BooleanField(default=False, help_text="If True, employee needs to refresh profile photo via selfie after login")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # User lookup optimization - OneToOne already creates index
            models.Index(fields=['user'], name='user_profile_user_idx'),
            # Organization filtering - O(1) queries
            models.Index(fields=['organization'], name='user_profile_org_idx'),
            # Custom employee ID lookup - already unique, but explicit index for clarity
            models.Index(fields=['custom_employee_id'], name='user_profile_emp_id_idx'),
            # Composite index for organization user queries
            models.Index(fields=['organization', 'user'], name='user_profile_org_user_idx'),
        ]

    def __str__(self):
        return self.user_name


class OrganizationSettings(models.Model): 
    id = models.BigAutoField(primary_key=True)
    organization = models.OneToOneField(BaseUserModel, on_delete=models.CASCADE, unique=True,limit_choices_to={'role': 'organization'},  related_name='own_organization_profile_setting')
    organization_logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True)
    face_recognition_enabled = models.BooleanField(default=False)
    auto_checkout_enabled = models.BooleanField(default=False)
    auto_checkout_time = models.TimeField(null=True, blank=True)
    auto_shiftwise_checkout_enabled = models.BooleanField(default=False)
    auto_shiftwise_checkout_in_minutes = models.IntegerField(null=True, blank=True, default=30, help_text="Grace period in minutes after shift end time")
    late_punch_enabled = models.BooleanField(default=False)
    late_punch_grace_minutes = models.IntegerField(null=True, blank=True)
    early_exit_enabled = models.BooleanField(default=False)
    early_exit_grace_minutes = models.IntegerField(null=True, blank=True)
    auto_shift_assignment_enabled = models.BooleanField(default=False)
    compensatory_off_enabled = models.BooleanField(default=False)
    custom_week_off_enabled = models.BooleanField(default=False)
    location_tracking_enabled = models.BooleanField(default=False)
    manual_attendance_enabled = models.BooleanField(default=False)
    group_location_tracking_enabled = models.BooleanField(default=False)
    location_marking_enabled = models.BooleanField(default=False)
    sandwich_leave_enabled = models.BooleanField(default=False)
    leave_carry_forward_enabled = models.BooleanField(default=False)
    min_hours_for_half_day = models.IntegerField(null=True, blank=True)
    multiple_shift_enabled = models.BooleanField(default=False)
    email_notifications_enabled = models.BooleanField(default=False)
    sms_notifications_enabled = models.BooleanField(default=False)
    push_notifications_enabled = models.BooleanField(default=False)
    ip_restriction_enabled = models.BooleanField(default=False)
    allowed_ip_ranges = models.TextField(blank=True, null=True)
    geofencing_enabled = models.BooleanField(default=False)
    geofence_radius_in_meters = models.IntegerField(null=True, blank=True)
    device_binding_enabled = models.BooleanField(default=False)
    plan_name = models.CharField(max_length=100, blank=True, null=True)
    plan_assigned_date = models.DateField(null=True, blank=True)
    plan_expiry_date = models.DateField(null=True, blank=True)
    
    # ==================== LEAVE YEAR CONFIGURATION ====================
    # Leave Year Type - Calendar, Financial, Custom
    leave_year_type = models.CharField(
        max_length=20,
        choices=[
            ('calendar', 'Calendar Year (Jan-Dec)'),
            ('financial', 'Financial Year (Apr-Mar)'),
            ('custom', 'Custom Year')
        ],
        default='calendar',
        help_text="Leave year type for leave balance calculation"
    )
    
    # Leave Year Start Month (1-12)
    leave_year_start_month = models.IntegerField(
        default=1,
        choices=[
            (1, 'January'), (2, 'February'), (3, 'March'),
            (4, 'April'), (5, 'May'), (6, 'June'),
            (7, 'July'), (8, 'August'), (9, 'September'),
            (10, 'October'), (11, 'November'), (12, 'December')
        ],
        help_text="Starting month for leave year (1-12)"
    )

    # ==================== SIDEBAR MENU CONTROL ====================
    # JSONField to store enabled/disabled menu items
    # Format: {"menu_base_key": true/false, ...}
    # Example: {"attendance": true, "allEmployees": true, "crm": false}
    enabled_menu_items = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary of menu items (by 'base' key) and their enabled status. If empty or key not present, menu item is enabled by default."
    )


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            # Organization lookup optimization - OneToOne already creates index
            models.Index(fields=['organization'], name='org_settings_org_idx'),
        ]



