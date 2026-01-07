"""
Advanced Leave Calculation Service
Handles leave calculations, accruals, carry forward, etc.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Sum
from .models import (
    LeaveType, LeavePolicy, EmployeeLeaveBalance,
    LeaveApplication, LeaveAccrualLog
)
try:
    from Holiday.models import Holiday
except ImportError:
    Holiday = None
from AuthN.models import BaseUserModel


class LeaveCalculator:
    """Advanced Leave Calculation Service"""
    
    def __init__(self, employee, leave_type, year=None):
        self.employee = employee
        self.leave_type = leave_type
        self.year = year or date.today().year
        self.user_profile = employee.own_user_profile
    
    def calculate_leave_days(self, from_date, to_date, include_weekends=False, include_holidays=False):
        """Calculate total leave days between dates"""
        if from_date > to_date:
            return Decimal('0.00')
        
        total_days = Decimal(str((to_date - from_date).days + 1))
        
        if not include_weekends:
            # Subtract weekends
            current_date = from_date
            weekend_days = Decimal('0.00')
            while current_date <= to_date:
                if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    weekend_days += Decimal('1.00')
                current_date += timedelta(days=1)
            total_days -= weekend_days
        
        if not include_holidays and Holiday:
            # Subtract holidays
            try:
                holidays = Holiday.objects.filter(
                    holiday_date__gte=from_date,
                    holiday_date__lte=to_date,
                    organization=self.user_profile.organization
                )
                holiday_count = Decimal(str(holidays.count()))
                total_days -= holiday_count
            except:
                pass
        
        return max(total_days, Decimal('0.00'))
    
    def get_leave_balance(self):
        """Get current leave balance"""
        balance = EmployeeLeaveBalance.objects.filter(
            user=self.employee,
            leave_type=self.leave_type,
            year=self.year,
            is_active=True
        ).first()
        
        if not balance:
            # Create balance if doesn't exist
            balance = self._create_leave_balance()
        
        return balance
    
    def _create_leave_balance(self):
        """Create leave balance for employee"""
        # Get current active admin using utility
        from utils.Employee.assignment_utils import get_current_admin_for_employee
        admin = get_current_admin_for_employee(self.employee)
        
        if not admin:
            raise ValueError("No active admin assignment found for this employee")
        
        organization = self.user_profile.organization
        
        # Get default allocation
        default_count = self.leave_type.default_count
        
        # Check for policy-based allocation
        policy = self._get_applicable_policy()
        if policy and self.leave_type.code in policy.leave_allocations:
            default_count = Decimal(str(policy.leave_allocations[self.leave_type.code]))
        
        balance = EmployeeLeaveBalance.objects.create(
            admin=admin,
            user=self.employee,
            leave_type=self.leave_type,
            year=self.year,
            assigned=default_count,
            opening_balance=default_count
        )
        
        return balance
    
    def _get_applicable_policy(self):
        """Get applicable leave policy for employee"""
        organization = self.user_profile.organization
        
        # Try employee-specific policy
        policy = LeavePolicy.objects.filter(
            organization=organization,
            scope='employee',
            scope_value=str(self.employee.id),
            effective_from__lte=date.today(),
            is_active=True
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=date.today())
        ).order_by('-effective_from').first()
        
        if policy:
            return policy
        
        # Try designation-based policy
        if hasattr(self.user_profile, 'designation') and self.user_profile.designation:
            policy = LeavePolicy.objects.filter(
                organization=organization,
                scope='designation',
                scope_value=self.user_profile.designation,
                effective_from__lte=date.today(),
                is_active=True
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=date.today())
            ).order_by('-effective_from').first()
            
            if policy:
                return policy
        
        # Try organization-wide policy
        policy = LeavePolicy.objects.filter(
            organization=organization,
            scope='organization',
            effective_from__lte=date.today(),
            is_active=True
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=date.today())
        ).order_by('-effective_from').first()
        
        return policy
    
    def check_leave_availability(self, from_date, to_date, total_days=None):
        """Check if leave can be availed"""
        balance = self.get_leave_balance()
        
        if total_days is None:
            policy = self._get_applicable_policy()
            include_weekends = policy.weekend_count_in_leave if policy else False
            include_holidays = policy.holiday_count_in_leave if policy else False
            total_days = self.calculate_leave_days(from_date, to_date, include_weekends, include_holidays)
        
        available_balance = balance.balance
        
        # Check pending leaves
        pending_leaves = LeaveApplication.objects.filter(
            user=self.employee,
            leave_type=self.leave_type,
            status__in=['pending', 'approved'],
            from_date__lte=to_date,
            to_date__gte=from_date
        ).exclude(id=getattr(self, 'current_application_id', None))
        
        pending_days = sum([app.total_days for app in pending_leaves])
        
        if available_balance - pending_days < total_days:
            return {
                'available': False,
                'message': f'Insufficient leave balance. Available: {available_balance - pending_days}, Required: {total_days}',
                'available_balance': available_balance - pending_days,
                'required_days': total_days
            }
        
        # Check minimum advance days
        if self.leave_type.min_advance_days > 0:
            days_in_advance = (from_date - date.today()).days
            if days_in_advance < self.leave_type.min_advance_days:
                return {
                    'available': False,
                    'message': f'Leave must be applied at least {self.leave_type.min_advance_days} days in advance',
                    'days_in_advance': days_in_advance,
                    'required_advance': self.leave_type.min_advance_days
                }
        
        # Check max consecutive days
        if self.leave_type.max_consecutive_days and total_days > self.leave_type.max_consecutive_days:
            return {
                'available': False,
                'message': f'Maximum {self.leave_type.max_consecutive_days} consecutive days allowed',
                'requested_days': total_days,
                'max_allowed': self.leave_type.max_consecutive_days
            }
        
        return {
            'available': True,
            'available_balance': available_balance - pending_days,
            'total_days': total_days
        }
    
    def process_leave_accrual(self, accrual_date=None):
        """Process leave accrual for employee"""
        if not self.leave_type.accrual_enabled:
            return None
        
        accrual_date = accrual_date or date.today()
        balance = self.get_leave_balance()
        
        # Check if already accrued for this period
        period_start, period_end = self._get_accrual_period(accrual_date)
        
        existing_log = LeaveAccrualLog.objects.filter(
            user=self.employee,
            leave_type=self.leave_type,
            accrual_period_start=period_start,
            accrual_period_end=period_end,
            is_processed=True
        ).first()
        
        if existing_log:
            return existing_log
        
        # Calculate days to accrue
        days_to_accrue = self.leave_type.accrual_rate
        
        # Create accrual log
        balance_before = balance.accrued
        balance.accrued += days_to_accrue
        balance.assigned += days_to_accrue
        balance.last_accrued_at = timezone.now()
        balance.save()
        
        accrual_log = LeaveAccrualLog.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            leave_balance=balance,
            accrual_date=accrual_date,
            accrual_period_start=period_start,
            accrual_period_end=period_end,
            days_accrued=days_to_accrue,
            balance_before=balance_before,
            balance_after=balance.accrued,
            is_processed=True,
            processed_at=timezone.now()
        )
        
        return accrual_log
    
    def _get_accrual_period(self, accrual_date):
        """Get accrual period start and end dates"""
        if self.leave_type.accrual_frequency == 'monthly':
            period_start = accrual_date.replace(day=1)
            if accrual_date.month == 12:
                period_end = accrual_date.replace(day=31)
            else:
                next_month = accrual_date.replace(month=accrual_date.month + 1, day=1)
                period_end = next_month - timedelta(days=1)
        elif self.leave_type.accrual_frequency == 'quarterly':
            quarter = (accrual_date.month - 1) // 3
            period_start = date(accrual_date.year, quarter * 3 + 1, 1)
            if quarter == 3:
                period_end = date(accrual_date.year, 12, 31)
            else:
                next_quarter_start = date(accrual_date.year, (quarter + 1) * 3 + 1, 1)
                period_end = next_quarter_start - timedelta(days=1)
        else:  # yearly
            period_start = date(accrual_date.year, 1, 1)
            period_end = date(accrual_date.year, 12, 31)
        
        return period_start, period_end
    
    def process_carry_forward(self, from_year, to_year):
        """Process carry forward from one year to next"""
        if not self.leave_type.carry_forward_enabled:
            return None
        
        from_balance = EmployeeLeaveBalance.objects.filter(
            user=self.employee,
            leave_type=self.leave_type,
            year=from_year,
            is_active=True
        ).first()
        
        if not from_balance:
            return None
        
        closing_balance = from_balance.closing_balance
        max_carry_forward = self.leave_type.max_carry_forward or closing_balance
        carry_forward_days = min(closing_balance, max_carry_forward)
        
        if carry_forward_days <= 0:
            return None
        
        # Update from year balance
        from_balance.carry_forward_to_next = carry_forward_days
        from_balance.save()
        
        # Update or create to year balance
        to_balance = EmployeeLeaveBalance.objects.filter(
            user=self.employee,
            leave_type=self.leave_type,
            year=to_year,
            is_active=True
        ).first()
        
        if not to_balance:
            # Get current active admin using utility
            from utils.Employee.assignment_utils import get_current_admin_for_employee
            admin = get_current_admin_for_employee(self.employee)
            
            if not admin:
                raise ValueError("No active admin assignment found for this employee")
            to_balance = EmployeeLeaveBalance.objects.create(
                admin=admin,
                user=self.employee,
                leave_type=self.leave_type,
                year=to_year,
                assigned=self.leave_type.default_count,
                opening_balance=self.leave_type.default_count
            )
        
        to_balance.carry_forward_from_previous = carry_forward_days
        to_balance.carried_forward = carry_forward_days
        to_balance.assigned += carry_forward_days
        
        # Set expiry date
        if self.leave_type.carry_forward_validity_months:
            expiry_date = date(to_year, 1, 1) + timedelta(days=30 * self.leave_type.carry_forward_validity_months)
            to_balance.carry_forward_expiry_date = expiry_date
        
        to_balance.save()
        
        return {
            'carried_forward': carry_forward_days,
            'from_year': from_year,
            'to_year': to_year
        }
    
    def calculate_leave_encashment(self, days_to_encash, daily_rate):
        """Calculate leave encashment amount"""
        if not self.leave_type.encashment_enabled:
            return None
        
        balance = self.get_leave_balance()
        
        # Check max encashment
        max_encashable = self.leave_type.max_encashment_days or balance.balance
        encashable_days = min(days_to_encash, max_encashable, balance.balance)
        
        if encashable_days <= 0:
            return None
        
        encashment_percentage = self.leave_type.encashment_percentage
        encashment_amount = (daily_rate * encashable_days * encashment_percentage) / 100
        
        return {
            'days_to_encash': encashable_days,
            'daily_rate': daily_rate,
            'encashment_percentage': encashment_percentage,
            'encashment_amount': encashment_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        }

