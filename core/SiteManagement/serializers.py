"""
Site Management Serializers
"""
from rest_framework import serializers
from .models import Site, EmployeeAdminSiteAssignment
from AuthN.models import BaseUserModel, AdminProfile, UserProfile


class SiteSerializer(serializers.ModelSerializer):
    """Serializer for Site read operations"""
    organization = serializers.CharField(source='organization.id', read_only=True)
    created_by_admin = serializers.CharField(source='created_by_admin.id', read_only=True)
    organization_name = serializers.SerializerMethodField()
    admin_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Site
        fields = [
            'id', 'organization', 'organization_name', 'created_by_admin', 'admin_name',
            'site_name', 'address', 'city', 'state', 'pincode', 'contact_person',
            'contact_number', 'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_by_admin', 'created_at', 'updated_at']
    
    def get_organization_name(self, obj):
        """Get organization name from OrganizationProfile"""
        try:
            if obj.organization and hasattr(obj.organization, 'own_organization_profile'):
                profile = obj.organization.own_organization_profile
                return profile.organization_name if profile else None
        except Exception:
            pass
        return None
    
    def get_admin_name(self, obj):
        """Get admin name from AdminProfile"""
        try:
            profile = obj.created_by_admin.own_admin_profile
            return profile.admin_name if profile else None
        except AdminProfile.DoesNotExist:
            return None


class SiteCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for Site create and update operations"""
    # Handle both 'name' and 'site_name' from frontend
    name = serializers.CharField(source='site_name', required=False, allow_blank=True)
    
    class Meta:
        model = Site
        fields = [
            'site_name', 'name', 'address', 'city', 'state', 'pincode', 'contact_person',
            'contact_number', 'description', 'is_active'
        ]
        extra_kwargs = {
            'site_name': {'required': False}
        }
    
    def validate(self, attrs):
        """Validate that admin belongs to organization"""
        # Handle 'name' field - map it to 'site_name' if provided
        if 'name' in attrs and 'site_name' not in attrs:
            attrs['site_name'] = attrs.pop('name')
        elif 'name' in attrs and 'site_name' in attrs:
            # If both provided, prefer 'site_name', remove 'name'
            attrs.pop('name', None)
        
        admin_id = self.context.get('admin_id')
        if admin_id:
            try:
                admin = BaseUserModel.objects.get(id=admin_id, role='admin')
                admin_profile = admin.own_admin_profile
                if admin_profile:
                    attrs['organization'] = admin_profile.organization
                    attrs['created_by_admin'] = admin
            except (BaseUserModel.DoesNotExist, AdminProfile.DoesNotExist):
                raise serializers.ValidationError("Invalid admin or admin profile not found")
        return attrs


class EmployeeAdminSiteAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeAdminSiteAssignment read operations"""
    employee_name = serializers.CharField(source='employee.own_user_profile.user_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    employee_id = serializers.CharField(source='employee.id', read_only=True)
    admin_name = serializers.SerializerMethodField()
    admin_email = serializers.CharField(source='admin.email', read_only=True)
    admin_id = serializers.CharField(source='admin.id', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    site_id = serializers.UUIDField(source='site.id', read_only=True)
    assigned_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeAdminSiteAssignment
        fields = [
            'id', 'employee', 'employee_id', 'employee_name', 'employee_email',
            'admin', 'admin_id', 'admin_name', 'admin_email',
            'site', 'site_id', 'site_name',
            'start_date', 'end_date', 'is_active',
            'assigned_by', 'assigned_by_name', 'assignment_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_admin_name(self, obj):
        """Get admin name from AdminProfile"""
        try:
            profile = obj.admin.own_admin_profile
            return profile.admin_name if profile else None
        except AdminProfile.DoesNotExist:
            return None
    
    def get_assigned_by_name(self, obj):
        """Get assigned_by user name"""
        if not obj.assigned_by:
            return None
        if obj.assigned_by.role == 'admin':
            try:
                profile = obj.assigned_by.own_admin_profile
                return profile.admin_name if profile else None
            except AdminProfile.DoesNotExist:
                return None
        elif obj.assigned_by.role == 'organization':
            try:
                profile = obj.assigned_by.own_organization_profile
                return profile.organization_name if profile else None
            except:
                return None
        return None


class EmployeeAdminSiteAssignmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating EmployeeAdminSiteAssignment with validation"""
    
    class Meta:
        model = EmployeeAdminSiteAssignment
        fields = [
            'admin', 'site', 'start_date', 'end_date', 'is_active',
            'assignment_reason'
        ]
    
    def validate(self, attrs):
        """Validate assignment data"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if end_date and start_date:
            if end_date < start_date:
                raise serializers.ValidationError({
                    'end_date': 'End date cannot be before start date'
                })
        
        # Validate admin and site belong to same organization
        admin = attrs.get('admin')
        site = attrs.get('site')
        
        if admin and site:
            try:
                admin_profile = admin.own_admin_profile
                if admin_profile and admin_profile.organization != site.organization:
                    raise serializers.ValidationError({
                        'site': 'Site must belong to the same organization as the admin'
                    })
            except AdminProfile.DoesNotExist:
                raise serializers.ValidationError({
                    'admin': 'Admin profile not found'
                })
        
        return attrs
    
    def create(self, validated_data):
        """
        Create assignment with assigned_by from context.
        
        When assigning employee to a different admin or site, this creates 2 entries:
        1. Old assignment entry: Updated with end_date (deactivated) - preserves history
           This maintains the record of which admin the employee worked under and for how long
        2. New assignment entry: Created with new site and admin (active)
        
        Only one active assignment per employee at a time.
        """
        employee = self.context.get('employee')
        assigned_by = self.context.get('assigned_by')
        
        if not employee:
            raise serializers.ValidationError("Employee context is required")
        
        from datetime import date, timedelta
        today = date.today()
        
        # Get new admin and site from validated_data
        new_admin = validated_data.get('admin')
        new_site = validated_data.get('site')
        
        # Get all active assignments for this employee
        # We will NOT deactivate them - both old and new assignments will remain active
        active_assignments = EmployeeAdminSiteAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('admin', 'site')
        
        # STEP 1: Keep old assignments active (do NOT deactivate)
        # Both old and new assignments will remain active
        # This allows tracking multiple active assignments for the same employee
        for assignment in active_assignments:
            # Check if admin or site is changing
            admin_changed = new_admin and assignment.admin != new_admin
            site_changed = new_site and assignment.site != new_site
            
            # Keep assignment active - do NOT set is_active = False
            # Do NOT set end_date - keep it None for active assignments
            # Just update assignment_reason if needed to track the change
            if not assignment.assignment_reason or (admin_changed or site_changed):
                reason_parts = []
                if admin_changed:
                    try:
                        old_admin_name = assignment.admin.own_admin_profile.admin_name if hasattr(assignment.admin, 'own_admin_profile') else assignment.admin.email
                        new_admin_name = new_admin.own_admin_profile.admin_name if hasattr(new_admin, 'own_admin_profile') else new_admin.email
                        reason_parts.append(f"Also assigned to Admin {new_admin_name}")
                    except:
                        reason_parts.append(f"Also assigned to new admin on {today}")
                
                if site_changed:
                    old_site_name = assignment.site.site_name if assignment.site else "No Site"
                    new_site_name = new_site.site_name if new_site else "No Site"
                    reason_parts.append(f"Also assigned to Site {new_site_name}")
                
                if reason_parts:
                    # Append to existing reason or create new
                    existing_reason = assignment.assignment_reason or ""
                    new_reason = f"{existing_reason}; {', '.join(reason_parts)} on {today}".strip('; ')
                    assignment.assignment_reason = new_reason
                    assignment.save()
            
            # Note: We do NOT deactivate the old assignment
            # Both old and new assignments will remain active
        
        # STEP 2: Create new assignment entry with new site/admin
        validated_data['employee'] = employee
        if assigned_by:
            validated_data['assigned_by'] = assigned_by
        
        # Ensure new assignment is active and start_date is set
        validated_data['is_active'] = True
        if 'start_date' not in validated_data or not validated_data['start_date']:
            validated_data['start_date'] = today
        
        # Set assignment_reason if not provided
        if 'assignment_reason' not in validated_data or not validated_data.get('assignment_reason'):
            reason_parts = []
            
            # Check if admin changed
            if active_assignments.exists():
                first_assignment = active_assignments.first()
                if new_admin and first_assignment.admin != new_admin:
                    try:
                        old_admin_name = first_assignment.admin.own_admin_profile.admin_name if hasattr(first_assignment.admin, 'own_admin_profile') else first_assignment.admin.email
                        new_admin_name = new_admin.own_admin_profile.admin_name if hasattr(new_admin, 'own_admin_profile') else new_admin.email
                        reason_parts.append(f"Transferred from Admin {old_admin_name} to Admin {new_admin_name}")
                    except:
                        reason_parts.append(f"Admin changed on {today}")
                
                # Check if site changed
                if new_site and first_assignment.site != new_site:
                    old_site_name = first_assignment.site.site_name if first_assignment.site else "No Site"
                    new_site_name = new_site.site_name if new_site else "No Site"
                    reason_parts.append(f"Site changed from {old_site_name} to {new_site_name}")
            
            if reason_parts:
                validated_data['assignment_reason'] = f"{', '.join(reason_parts)} on {today}"
            else:
                validated_data['assignment_reason'] = f"New assignment created on {today}"
        
        # Create the new assignment entry (second entry)
        new_assignment = super().create(validated_data)
        
        return new_assignment


class EmployeeAdminSiteAssignmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating EmployeeAdminSiteAssignment"""
    
    class Meta:
        model = EmployeeAdminSiteAssignment
        fields = [
            'site', 'start_date', 'end_date', 'is_active', 'assignment_reason'
        ]
    
    def validate(self, attrs):
        """Validate update data"""
        start_date = attrs.get('start_date', self.instance.start_date)
        end_date = attrs.get('end_date', self.instance.end_date)
        is_active = attrs.get('is_active', self.instance.is_active)
        site = attrs.get('site', self.instance.site)
        
        if end_date and start_date:
            if end_date < start_date:
                raise serializers.ValidationError({
                    'end_date': 'End date cannot be before start date'
                })
        
        # If making this assignment active, deactivate all other active assignments
        # This maintains history by preserving old assignments with end_date
        if is_active and site:
            from datetime import date
            today = date.today()
            
            # Get all other active assignments for this employee
            other_active = EmployeeAdminSiteAssignment.objects.filter(
                employee=self.instance.employee,
                is_active=True
            ).exclude(id=self.instance.id)
            
            # Deactivate them and set end_date (preserving history)
            for assignment in other_active:
                assignment.is_active = False
                if not assignment.end_date or assignment.end_date > today:
                    assignment.end_date = today
                assignment.save()
        
        return attrs

