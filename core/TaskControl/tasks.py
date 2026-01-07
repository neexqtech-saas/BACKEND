"""
Celery Tasks for Task Scheduling
Optimized O(1) complexity scheduling
"""

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db import transaction
from .models import Task
from AuthN.models import BaseUserModel
import logging

logger = logging.getLogger(__name__)


@shared_task
def create_scheduled_task(task_id):
    """
    Create a scheduled task instance from parent task
    O(1) complexity - direct task creation
    """
    try:
        with transaction.atomic():
            parent_task = Task.objects.select_for_update().get(id=task_id)
            
            # Check if schedule has ended
            if parent_task.schedule_end_date and parent_task.schedule_end_date < date.today():
                logger.info(f"Schedule ended for task {task_id}")
                return {"status": "ended", "task_id": task_id}
            
            # Calculate next due date based on frequency
            next_due_date = calculate_next_due_date(parent_task)
            if not next_due_date:
                logger.warning(f"Could not calculate next due date for task {task_id}")
                return {"status": "error", "task_id": task_id}
            
            # Create new task instance
            new_task = Task.objects.create(
                admin=parent_task.admin,
                task_type=parent_task.task_type,
                title=parent_task.title,
                description=parent_task.description,
                priority=parent_task.priority,
                status='pending',
                assigned_to=parent_task.assigned_to,
                assigned_by=parent_task.assigned_by,
                start_date=next_due_date,
                due_date=next_due_date,
                schedule_frequency='onetime',  # Instance is always onetime
                parent_task=parent_task,
                is_scheduled_instance=True,
                tags=parent_task.tags,
                checklist=parent_task.checklist,
            )
            
            logger.info(f"Created scheduled task instance {new_task.id} from parent {task_id}")
            return {"status": "success", "task_id": new_task.id, "parent_id": task_id}
            
    except Task.DoesNotExist:
        logger.error(f"Parent task {task_id} not found")
        return {"status": "error", "message": "Parent task not found"}
    except Exception as e:
        logger.error(f"Error creating scheduled task: {str(e)}")
        return {"status": "error", "message": str(e)}


def calculate_next_due_date(task):
    """
    Calculate next due date based on schedule frequency
    O(1) complexity - direct date calculation
    """
    today = date.today()
    
    if task.schedule_frequency == 'daily':
        # Next day
        return today + timedelta(days=1)
    
    elif task.schedule_frequency == 'weekly':
        if not task.week_day:
            return None
        
        # Get current weekday (0=Monday, 6=Sunday)
        current_weekday = today.weekday()
        target_weekday = int(task.week_day)
        
        # Calculate days until next occurrence
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:  # Target day already passed this week
            days_ahead += 7
        
        return today + timedelta(days=days_ahead)
    
    elif task.schedule_frequency == 'monthly':
        if not task.month_date:
            return None
        
        # Get next month
        if today.month == 12:
            next_month = 1
            next_year = today.year + 1
        else:
            next_month = today.month + 1
            next_year = today.year
        
        # Handle month_date (1-31)
        try:
            return date(next_year, next_month, min(task.month_date, 28))  # Safe date
        except ValueError:
            # If date doesn't exist (e.g., Feb 30), use last day of month
            from calendar import monthrange
            last_day = monthrange(next_year, next_month)[1]
            return date(next_year, next_month, min(task.month_date, last_day))
    
    return None


@shared_task
def process_daily_schedules():
    """
    Process all daily scheduled tasks
    O(n) where n = number of daily tasks (optimized with index)
    """
    today = date.today()
    
    # Get all active daily scheduled tasks
    daily_tasks = Task.objects.filter(
        schedule_frequency='daily',
        is_scheduled_instance=False,
        schedule_end_date__gte=today
    ).select_related('admin', 'task_type', 'assigned_to', 'assigned_by')
    
    created_count = 0
    for task in daily_tasks:
        # Check if task already created for today
        existing = Task.objects.filter(
            parent_task=task,
            is_scheduled_instance=True,
            due_date=today
        ).exists()
        
        if not existing:
            create_scheduled_task.delay(task.id)
            created_count += 1
    
    logger.info(f"Processed {created_count} daily scheduled tasks")
    return {"status": "success", "created": created_count}


@shared_task
def process_weekly_schedules():
    """
    Process all weekly scheduled tasks
    O(n) where n = number of weekly tasks (optimized with index)
    """
    today = date.today()
    current_weekday = today.weekday()  # 0=Monday, 6=Sunday
    
    # Get all active weekly scheduled tasks for today's weekday
    weekly_tasks = Task.objects.filter(
        schedule_frequency='weekly',
        week_day=str(current_weekday),
        is_scheduled_instance=False,
        schedule_end_date__gte=today
    ).select_related('admin', 'task_type', 'assigned_to', 'assigned_by')
    
    created_count = 0
    for task in weekly_tasks:
        # Check if task already created for today
        existing = Task.objects.filter(
            parent_task=task,
            is_scheduled_instance=True,
            due_date=today
        ).exists()
        
        if not existing:
            create_scheduled_task.delay(task.id)
            created_count += 1
    
    logger.info(f"Processed {created_count} weekly scheduled tasks for weekday {current_weekday}")
    return {"status": "success", "created": created_count}


@shared_task
def process_monthly_schedules():
    """
    Process all monthly scheduled tasks
    O(n) where n = number of monthly tasks (optimized with index)
    """
    today = date.today()
    current_date = today.day
    
    # Get all active monthly scheduled tasks for today's date
    monthly_tasks = Task.objects.filter(
        schedule_frequency='monthly',
        month_date=current_date,
        is_scheduled_instance=False,
        schedule_end_date__gte=today
    ).select_related('admin', 'task_type', 'assigned_to', 'assigned_by')
    
    created_count = 0
    for task in monthly_tasks:
        # Check if task already created for this month
        existing = Task.objects.filter(
            parent_task=task,
            is_scheduled_instance=True,
            due_date__year=today.year,
            due_date__month=today.month
        ).exists()
        
        if not existing:
            create_scheduled_task.delay(task.id)
            created_count += 1
    
    logger.info(f"Processed {created_count} monthly scheduled tasks for date {current_date}")
    return {"status": "success", "created": created_count}

