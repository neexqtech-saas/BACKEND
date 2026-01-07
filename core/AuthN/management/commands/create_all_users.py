from django.core.management.base import BaseCommand
from django.db import transaction
from AuthN.models import (
    BaseUserModel, 
    SystemOwnerProfile, 
    OrganizationProfile, 
    AdminProfile, 
    UserProfile,
    OrganizationSettings
)
from ServiceShift.models import ServiceShift
from ServiceWeekOff.models import WeekOffPolicy
from TaskControl.models import TaskType
from Expenditure.models import ExpenseCategory
from LocationControl.models import Location
from SiteManagement.models import EmployeeAdminSiteAssignment, Site
from django.utils import timezone


class Command(BaseCommand):
    help = 'Creates all four types of users: SystemOwner, Organization, Admin, and User'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Delete existing users and recreate them',
        )

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write(self.style.SUCCESS('Starting user registration...'))
        
        try:
            with transaction.atomic():
                # 1. Create System Owner
                self.stdout.write('Creating System Owner...')
                system_owner_data = {
                    "user": {
                        "email": "sysowner@gmail.com",
                        "username": "systemowner",
                        "password": "testpassword",
                        "role": "system_owner",
                        "phone_number": "9876543210"
                    },
                    "company_name": "Tech Corp"
                }
                
                # Check if user exists
                existing_system_owner = BaseUserModel.objects.filter(
                    email=system_owner_data["user"]["email"]
                ).first()
                
                if existing_system_owner:
                    if force:
                        self.stdout.write(self.style.WARNING(f'Deleting existing System Owner: {existing_system_owner.email}'))
                        SystemOwnerProfile.objects.filter(user=existing_system_owner).delete()
                        existing_system_owner.delete()
                    else:
                        self.stdout.write(self.style.WARNING(f'System Owner already exists: {existing_system_owner.email}. Use --force to recreate.'))
                        system_owner_user = existing_system_owner
                        system_owner_profile = SystemOwnerProfile.objects.get(user=system_owner_user)
                
                if not existing_system_owner or force:
                    system_owner_user = BaseUserModel.objects.create_user(
                        email=system_owner_data["user"]["email"],
                        username=system_owner_data["user"]["username"],
                        password=system_owner_data["user"]["password"],
                        role="system_owner",
                        phone_number=system_owner_data["user"]["phone_number"]
                    )
                    system_owner_profile = SystemOwnerProfile.objects.create(
                        user=system_owner_user,
                        company_name=system_owner_data["company_name"]
                    )
                    self.stdout.write(self.style.SUCCESS(f'[OK] System Owner created: {system_owner_user.email}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'[OK] Using existing System Owner: {system_owner_user.email}'))
                
                # 2. Create Organization
                self.stdout.write('Creating Organization...')
                organization_data = {
                    "user": {
                        "email": "organizati1on1a1a@gmail.com",
                        "username": "systemorganization",
                        "password": "testpassword",
                        "role": "organization",
                        "phone_number": "9876543211"
                    },
                    "organization_name": "Tech Corp"
                }
                
                existing_organization = BaseUserModel.objects.filter(
                    email=organization_data["user"]["email"]
                ).first()
                
                if existing_organization:
                    if force:
                        self.stdout.write(self.style.WARNING(f'Deleting existing Organization: {existing_organization.email}'))
                        OrganizationProfile.objects.filter(user=existing_organization).delete()
                        OrganizationSettings.objects.filter(organization=existing_organization).delete()
                        existing_organization.delete()
                    else:
                        self.stdout.write(self.style.WARNING(f'Organization already exists: {existing_organization.email}. Use --force to recreate.'))
                        organization_user = existing_organization
                        organization_profile = OrganizationProfile.objects.get(user=organization_user)
                
                if not existing_organization or force:
                    organization_user = BaseUserModel.objects.create_user(
                        email=organization_data["user"]["email"],
                        username=organization_data["user"]["username"],
                        password=organization_data["user"]["password"],
                        role="organization",
                        phone_number=organization_data["user"]["phone_number"]
                    )
                    organization_profile = OrganizationProfile.objects.create(
                        user=organization_user,
                        organization_name=organization_data["organization_name"],
                        system_owner=system_owner_user,
                        state="Maharashtra",
                        city="Mumbai"
                    )
                    # Create OrganizationSettings
                    OrganizationSettings.objects.create(organization=organization_user)
                    self.stdout.write(self.style.SUCCESS(f'[OK] Organization created: {organization_user.email}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'[OK] Using existing Organization: {organization_user.email}'))
                
                # 3. Create Admin
                self.stdout.write('Creating Admin...')
                admin_data = {
                    "user": {
                        "email": "aadminq11a11aq@gmail.com",
                        "username": "systemadmin",
                        "password": "testpassword",
                        "role": "admin",
                        "phone_number": "9876543212"
                    },
                    "admin_name": "Tech Corp Admin"
                }
                
                existing_admin = BaseUserModel.objects.filter(
                    email=admin_data["user"]["email"]
                ).first()
                
                if existing_admin:
                    if force:
                        self.stdout.write(self.style.WARNING(f'Deleting existing Admin: {existing_admin.email}'))
                        # Delete related data first
                        EmployeeAdminSiteAssignment.objects.filter(admin=existing_admin).delete()
                        Site.objects.filter(created_by_admin=existing_admin).delete()
                        AdminProfile.objects.filter(user=existing_admin).delete()
                        ServiceShift.objects.filter(admin=existing_admin).delete()
                        WeekOffPolicy.objects.filter(admin=existing_admin).delete()
                        TaskType.objects.filter(admin=existing_admin).delete()
                        ExpenseCategory.objects.filter(admin=existing_admin).delete()
                        existing_admin.delete()
                    else:
                        self.stdout.write(self.style.WARNING(f'Admin already exists: {existing_admin.email}. Use --force to recreate.'))
                        admin_user = existing_admin
                        admin_profile = AdminProfile.objects.get(user=admin_user)
                
                if not existing_admin or force:
                    admin_user = BaseUserModel.objects.create_user(
                        email=admin_data["user"]["email"],
                        username=admin_data["user"]["username"],
                        password=admin_data["user"]["password"],
                        role="admin",
                        phone_number=admin_data["user"]["phone_number"]
                    )
                    admin_profile = AdminProfile.objects.create(
                        user=admin_user,
                        admin_name=admin_data["admin_name"],
                        organization=organization_user,
                        state="Maharashtra",
                        city="Mumbai"
                    )
                    # Create default ServiceShift, WeekOffPolicy, TaskType, ExpenseCategory
                    ServiceShift.objects.create(admin=admin_user)
                    WeekOffPolicy.objects.create(admin=admin_user)
                    WeekOffPolicy.objects.create(admin=admin_user)
                    TaskType.objects.create(admin=admin_user)
                    ExpenseCategory.objects.create(admin=admin_user)
                    
                    # Create default Site for admin
                    default_site = Site.objects.create(
                        organization=organization_user,
                        created_by_admin=admin_user,
                        site_name="Main Site",
                        address="Default Address",
                        city="Mumbai",
                        state="Maharashtra",
                        pincode="400001",
                        contact_person=admin_data["admin_name"],
                        contact_number=admin_data["user"]["phone_number"],
                        description="Default site created for admin",
                        is_active=True
                    )
                    self.stdout.write(self.style.SUCCESS(f'[OK] Admin created: {admin_user.email}'))
                    self.stdout.write(self.style.SUCCESS(f'[OK] Default site created: {default_site.site_name}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'[OK] Using existing Admin: {admin_user.email}'))
                    # Ensure default site exists for existing admin
                    existing_site = Site.objects.filter(
                        created_by_admin=admin_user,
                        is_active=True
                    ).first()
                    if not existing_site:
                        default_site = Site.objects.create(
                            organization=organization_user,
                            created_by_admin=admin_user,
                            site_name="Main Site",
                            address="Default Address",
                            city="Mumbai",
                            state="Maharashtra",
                            pincode="400001",
                            contact_person=admin_profile.admin_name,
                            contact_number=admin_user.phone_number or "0000000000",
                            description="Default site created for existing admin",
                            is_active=True
                        )
                        self.stdout.write(self.style.WARNING(f'[INFO] Created default site for existing admin: {default_site.site_name}'))
                
                # 4. Create User
                self.stdout.write('Creating User...')
                user_data = {
                    "user": {
                        "email": "user111q1aa131@gmail.com",
                        "username": "systemuser",
                        "password": "testpassword",
                        "role": "user",
                        "phone_number": "9876543213"
                    },
                    "user_name": "Tech Corp user"
                }
                
                existing_user = BaseUserModel.objects.filter(
                    email=user_data["user"]["email"]
                ).first()
                
                if existing_user:
                    if force:
                        self.stdout.write(self.style.WARNING(f'Deleting existing User: {existing_user.email}'))
                        UserProfile.objects.filter(user=existing_user).delete()
                        existing_user.delete()
                    else:
                        self.stdout.write(self.style.WARNING(f'User already exists: {existing_user.email}. Use --force to recreate.'))
                        user_user = existing_user
                        user_profile = UserProfile.objects.get(user=user_user)
                
                if not existing_user or force:
                    user_user = BaseUserModel.objects.create_user(
                        email=user_data["user"]["email"],
                        username=user_data["user"]["username"],
                        password=user_data["user"]["password"],
                        role="user",
                        phone_number=user_data["user"]["phone_number"]
                    )
                    # Generate unique employee ID if EMP001 already exists
                    base_emp_id = "EMP001"
                    emp_id = base_emp_id
                    counter = 1
                    while UserProfile.objects.filter(custom_employee_id=emp_id).exists():
                        counter += 1
                        emp_id = f"EMP{counter:03d}"
                    
                    user_profile = UserProfile.objects.create(
                        user=user_user,
                        user_name=user_data["user_name"],
                        admin=admin_user,
                        organization=organization_user,
                        date_of_joining=timezone.now().date(),
                        gender="Male",
                        custom_employee_id=emp_id,
                        state="Maharashtra",
                        city="Mumbai"
                    )
                    # Assign defaults (M2M fields)
                    shift_ids = ServiceShift.objects.filter(admin=admin_user, is_active=True).values_list('id', flat=True)[:1]
                    week_off_ids = WeekOffPolicy.objects.filter(admin=admin_user).values_list('id', flat=True)[:1]
                    location_ids = Location.objects.filter(admin=admin_user, is_active=True).values_list('id', flat=True)[:1]
                    
                    if shift_ids:
                        user_profile.shifts.set(shift_ids)
                    if week_off_ids:
                        user_profile.week_offs.set(week_off_ids)
                    if location_ids:
                        user_profile.locations.set(location_ids)
                    
                    # Create EmployeeAdminSiteAssignment with admin's default site
                    # Get or create default site if it doesn't exist
                    default_site = Site.objects.filter(
                        created_by_admin=admin_user,
                        is_active=True
                    ).order_by('created_at').first()
                    
                    # If no site exists, create one
                    if not default_site:
                        default_site = Site.objects.create(
                            organization=organization_user,
                            created_by_admin=admin_user,
                            site_name="Main Site",
                            address="Default Address",
                            city="Mumbai",
                            state="Maharashtra",
                            pincode="400001",
                            contact_person=admin_profile.admin_name,
                            contact_number=admin_user.phone_number or "0000000000",
                            description="Default site created during user assignment",
                            is_active=True
                        )
                        self.stdout.write(self.style.WARNING(f'[INFO] Created default site for user assignment: {default_site.site_name}'))
                    
                    # Create employee assignment
                    EmployeeAdminSiteAssignment.objects.create(
                        employee=user_user,
                        admin=admin_user,
                        site=default_site,
                        start_date=timezone.now().date(),
                        end_date=None,
                        is_active=True,
                        assigned_by=admin_user,
                        assignment_reason='Initial assignment during user creation'
                    )
                    
                    self.stdout.write(self.style.SUCCESS(f'[OK] User created: {user_user.email}'))
                    self.stdout.write(self.style.SUCCESS(f'[OK] User assigned to site: {default_site.site_name}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'[OK] Using existing User: {user_user.email}'))
                
                self.stdout.write(self.style.SUCCESS('\n' + '='*50))
                self.stdout.write(self.style.SUCCESS('All users created successfully!'))
                self.stdout.write(self.style.SUCCESS('='*50))
                self.stdout.write(self.style.SUCCESS(f'\nSystem Owner: {system_owner_user.email}'))
                self.stdout.write(self.style.SUCCESS(f'Organization: {organization_user.email}'))
                self.stdout.write(self.style.SUCCESS(f'Admin: {admin_user.email}'))
                self.stdout.write(self.style.SUCCESS(f'User: {user_user.email}'))
                self.stdout.write(self.style.SUCCESS('\nAll users password: testpassword'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating users: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise

