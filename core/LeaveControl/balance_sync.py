"""
Helper function to sync leave balance based on actual leave applications
"""
from decimal import Decimal
from django.db import models
from .models import EmployeeLeaveBalance, LeaveApplication


def sync_leave_balance(user_id, leave_type_id, year):
    """
    Recalculate and sync 'used' count based on all pending + approved leaves
    This ensures accuracy and fixes any inconsistencies
    """
    # Get the balance record
    balance = EmployeeLeaveBalance.objects.filter(
        user__id=user_id,
        leave_type_id=leave_type_id,
        year=year
    ).first()
    
    if not balance:
        print(f"❌ Balance not found for user={user_id}, leave_type={leave_type_id}, year={year}")
        return None
    
    # Calculate total used from all pending + approved leaves
    total_used = LeaveApplication.objects.filter(
        user__id=user_id,
        leave_type_id=leave_type_id,
        from_date__year=year,
        status__in=['pending', 'approved']
    ).aggregate(
        total=models.Sum('total_days')
    )['total'] or 0
    
    # Update balance
    old_used = balance.used
    balance.used = Decimal(str(total_used))
    balance.save()
    
    print(f"✅ Balance synced: user={user_id}, leave_type={leave_type_id}, year={year}")
    print(f"   Old used: {old_used}, New used: {balance.used}, Change: {balance.used - Decimal(str(old_used))}")
    
    return balance

