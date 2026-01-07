"""
Celery Tasks for Core Application
"""

# Conditional import to avoid circular import when running directly
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Create a dummy decorator when celery is not available
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from django.utils import timezone
from datetime import datetime, timedelta, date, time
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
import logging
import traceback

logger = logging.getLogger(__name__)


@shared_task(name='general_auto_checkout_task')
def general_auto_checkout_task():
    """
    Handles general auto-checkout for organizations.
    This checks out all pending users at a fixed time defined by the organization.
    This task should be run periodically (e.g., every 5-10 minutes) by a scheduler.
    """
    from AuthN.models import OrganizationSettings
    from WorkLog.models import Attendance
    
    now = timezone.now()
    current_date = now.date()
    logger.info(f"--- Running General Auto-Checkout Task at {now} ---")
    
    try:
        # Get organizations with general auto-checkout enabled (and shift-wise disabled to avoid conflict).
        general_settings = OrganizationSettings.objects.filter(
            auto_checkout_enabled=True,
            auto_shiftwise_checkout_enabled=False,  # Ensure shift-wise is off to prevent conflicts.
            auto_checkout_time__isnull=False,
        )
        print(general_settings)
        
        for setting in general_settings:
            # Proceed only if the current time is past the organization's auto-checkout time.
            if now.time() >= setting.auto_checkout_time:
                attendances_to_checkout = Attendance.objects.filter(
                    user__own_user_profile__organization=setting.organization,
                    attendance_date=current_date,
                    check_in_time__isnull=False,
                    check_out_time__isnull=True
                )
                
                checkout_datetime = datetime.combine(current_date, setting.auto_checkout_time)
                # Since USE_TZ = False, use naive datetime
                checkout_datetime_naive = checkout_datetime
                
                updates_to_perform = []
                for attendance in attendances_to_checkout:
                    attendance.check_out_time = checkout_datetime_naive
                    attendance.remarks = (attendance.remarks or "") + "\nAuto checked-out by system (General)."
                    if attendance.check_in_time:
                        # Ensure check_in_time is naive for calculation (USE_TZ = False)
                        check_in_time_naive = attendance.check_in_time
                        if timezone.is_aware(check_in_time_naive):
                            check_in_time_naive = timezone.make_naive(check_in_time_naive, timezone.get_current_timezone())
                        total_seconds = (checkout_datetime_naive - check_in_time_naive).total_seconds()
                        attendance.total_working_minutes = int(total_seconds // 60)
                    updates_to_perform.append(attendance)
                
                if updates_to_perform:
                    Attendance.objects.bulk_update(updates_to_perform, ['check_out_time', 'remarks', 'total_working_minutes'])
                    logger.info(f"[General] Auto-checked out {len(updates_to_perform)} users for organization: {setting.organization.email}")
        
        logger.info("--- General Auto-Checkout Task Finished ---")
        return {"status": "success", "message": "General auto-checkout completed"}
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in general_auto_checkout_task: {str(e)}\nTraceback:\n{error_traceback}")
        return {"status": "error", "message": str(e)}


@shared_task(name='shiftwise_auto_checkout_task')
def shiftwise_auto_checkout_task():
    """
    Handles shift-wise auto-checkout for organizations.
    This checks out users based on their assigned shift's end time plus a grace period.
    This task should be run periodically (e.g., every 5-10 minutes) by a scheduler.
    """
    from AuthN.models import OrganizationSettings
    from WorkLog.models import Attendance
    
    now = timezone.now()
    current_date = now.date()
    logger.info(f"--- Running Shift-Wise Auto-Checkout Task at {now} ---")
    
    try:
        shiftwise_settings = OrganizationSettings.objects.filter(
            auto_shiftwise_checkout_enabled=True
        )
        
        for setting in shiftwise_settings:
            # Find pending checkouts from today AND yesterday to handle night shifts.
            # A shift starting late yesterday might end today.
            yesterday = current_date - timedelta(days=1)
            
            pending_attendances = Attendance.objects.filter(
                user__own_user_profile__organization=setting.organization,
                attendance_date__in=[current_date, yesterday],
                check_in_time__isnull=False,
                check_out_time__isnull=True,
                assign_shift__isnull=False,
                assign_shift__end_time__isnull=False,
                assign_shift__start_time__isnull=False,
            ).select_related('assign_shift')  # Use select_related for performance
            
            updates_to_perform = []
            
            for attendance in pending_attendances:
                shift_end_time = attendance.assign_shift.end_time
                grace_period_minutes = setting.auto_shiftwise_checkout_in_minutes or 30  # Use configured grace period or default 30 minutes
                
                # Determine if it's a night shift (ends on the next day)
                is_night_shift = attendance.assign_shift.end_time < attendance.assign_shift.start_time
                
                # The checkout date is the next day if it's a night shift
                checkout_date = attendance.attendance_date
                if is_night_shift:
                    checkout_date += timedelta(days=1)
                
                # Create a timedelta object for the grace period.
                grace_delta = timedelta(minutes=grace_period_minutes)
                
                # Calculate the exact time when auto-checkout should be triggered.
                # This is based on the calculated checkout_date.
                trigger_datetime = datetime.combine(checkout_date, shift_end_time) + grace_delta
                # Since USE_TZ = False, use naive datetime
                trigger_datetime_naive = trigger_datetime
                
                # Check if the current time has passed the trigger time.
                # Convert now to naive if needed
                now_naive = now
                if timezone.is_aware(now_naive):
                    now_naive = timezone.make_naive(now_naive, timezone.get_current_timezone())
                
                if now_naive >= trigger_datetime_naive:
                    # As requested, the checkout time should be the shift's end time.
                    checkout_datetime = datetime.combine(checkout_date, shift_end_time)
                    # Since USE_TZ = False, use naive datetime
                    checkout_datetime_naive = checkout_datetime
                    
                    attendance.check_out_time = checkout_datetime_naive
                    attendance.remarks = (attendance.remarks or "") + "\nAuto checked-out by system (Shift-wise)."
                    if attendance.check_in_time:
                        # Ensure check_in_time is naive for calculation (USE_TZ = False)
                        check_in_time_naive = attendance.check_in_time
                        if timezone.is_aware(check_in_time_naive):
                            check_in_time_naive = timezone.make_naive(check_in_time_naive, timezone.get_current_timezone())
                        total_seconds = (checkout_datetime_naive - check_in_time_naive).total_seconds()
                        attendance.total_working_minutes = int(total_seconds // 60)
                    
                    updates_to_perform.append(attendance)
            
            if updates_to_perform:
                Attendance.objects.bulk_update(updates_to_perform, ['check_out_time', 'remarks', 'total_working_minutes'])
                logger.info(f"[Shift-Wise] Auto-checked out {len(updates_to_perform)} users for organization: {setting.organization.email}")
        
        logger.info("--- Shift-Wise Auto-Checkout Task Finished ---")
        return {"status": "success", "message": "Shift-wise auto-checkout completed"}
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in shiftwise_auto_checkout_task: {str(e)}\nTraceback:\n{error_traceback}")
        return {"status": "error", "message": str(e)}

