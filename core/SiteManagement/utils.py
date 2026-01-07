"""
Utility functions for Site Management
"""
from datetime import time
from ServiceShift.models import ServiceShift
from ServiceWeekOff.models import WeekOffPolicy
from LeaveControl.models import LeaveType
from TaskControl.models import TaskType
from Expenditure.models import ExpenseCategory


def create_default_site_resources(admin, site):
    """
    Create default resources (Shift, Week Off, Leave Type, Task Type, Expense Category) for a site.
    
    Args:
        admin: BaseUserModel instance with role='admin'
        site: Site instance
    """
    # Create default ServiceShift
    ServiceShift.objects.create(
        admin=admin,
        site=site,
        shift_name="Default Shift",
        start_time=time(9, 0),
        end_time=time(18, 0),
        is_active=True
    )
    
    # Create default WeekOffPolicy
    WeekOffPolicy.objects.create(
        admin=admin,
        site=site,
        name="Default Week Off",
        week_off_type="Default",
        is_active=True
    )
    
    # Create default LeaveType - Only Sick Leave
    LeaveType.objects.create(
        admin=admin,
        site=site,
        name="Sick Leave",
        code="SL",
        default_count=12.00,
        is_paid=True,
        is_active=True
    )
    
    # Create default TaskType
    TaskType.objects.create(
        admin=admin,
        site=site,
        name="Service Task",
        description="Default task type",
        is_active=True
    )
    
    # Create default ExpenseCategory
    ExpenseCategory.objects.create(
        admin=admin,
        site=site,
        name="Service Expense",
        description="Default expense category",
        is_active=True
    )

