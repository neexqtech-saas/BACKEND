from datetime import datetime, timedelta, date
from ServiceShift.models import ServiceShift


def get_nearest_shift_with_late_minutes(checkin_time, assigned_shifts_list):
    """
    Optimized: Finds the nearest shift based on check-in time and calculates late minutes.
    Accepts list instead of queryset for better performance.
    Returns: (nearest_shift_object, late_minutes)
    """
    if not assigned_shifts_list:
        return None, 0

    nearest_shift = None
    min_diff_seconds = float('inf')
    checkin_date = checkin_time.date()

    # Handle timezone-aware datetime comparison
    checkin_time_naive = checkin_time
    if checkin_time.tzinfo is not None:
        checkin_time_naive = checkin_time.replace(tzinfo=None)
    
    for shift in assigned_shifts_list:
        shift_start = datetime.combine(checkin_date, shift.start_time)
        diff_seconds = abs((shift_start - checkin_time_naive).total_seconds())

        if diff_seconds < min_diff_seconds:
            min_diff_seconds = diff_seconds
            nearest_shift = shift

    if nearest_shift:
        shift_start = datetime.combine(checkin_date, nearest_shift.start_time)
        if checkin_time_naive > shift_start:
            late_minutes = int((checkin_time_naive - shift_start).total_seconds() // 60)
        else:
            late_minutes = 0
    else:
        late_minutes = 0

    return nearest_shift, late_minutes



def calculate_total_working_minutes(check_in, check_out):
    # Handle timezone-aware datetime comparison
    check_in_naive = check_in.replace(tzinfo=None) if check_in.tzinfo is not None else check_in
    check_out_naive = check_out.replace(tzinfo=None) if check_out.tzinfo is not None else check_out
    total_seconds = (check_out_naive - check_in_naive).total_seconds()
    if total_seconds < 10:  # Minimum 10 seconds required
        return None  
    return int(total_seconds // 60)  # Convert to minutes for storage


def calculate_early_exit_minutes(check_out, shift_end_time):
    # Handle timezone-aware datetime comparison
    checkout_time = check_out
    # Convert to naive datetime if timezone-aware, or keep as-is if naive
    if checkout_time.tzinfo is not None:
        checkout_time = checkout_time.replace(tzinfo=None)
    
    shift_end = datetime.combine(checkout_time.date(), shift_end_time)

    if checkout_time < shift_end:
        early_seconds = (shift_end - checkout_time).total_seconds()
        return int(early_seconds // 60)

    return 0


def calculate_overtime_minutes(total_minutes, expected_hours=8):
    if total_minutes is None:
        return 0
    expected_minutes = expected_hours * 60
    extra = total_minutes - expected_minutes

    return int(extra) if extra > 0 else 0

def format_datetime(dt):
    """Format datetime to 'YYYY-MM-DD HH:MM:SS' """
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return str(dt)


def format_date(d):
    """Format date to 'YYYY-MM-DD' """
    if not d:
        return None
    if isinstance(d, date):
        return d.strftime('%Y-%m-%d')
    return str(d)


def format_minutes(minutes):
    """Convert minutes → 'Xh Ym' """
    if not minutes or minutes <= 0:
        return "0h 0m"
    return f"{minutes // 60}h {minutes % 60}m"


def format_break(obj):
    """Break duration formatter"""
    break_minutes = obj.get('total_break_minutes', 0) if isinstance(obj, dict) else getattr(obj, 'break_duration_minutes', 0)
    return format_minutes(break_minutes)


def format_production_hours(obj):
    """Working duration formatter"""
    total_minutes = obj.get('total_working_minutes', 0) if isinstance(obj, dict) else getattr(obj, 'total_working_minutes', 0)
    return format_minutes(total_minutes)


def format_late_minutes(obj):
    """Late minutes formatted"""
    late_minutes = obj.get('late_minutes', 0) if isinstance(obj, dict) else getattr(obj, 'late_minutes', 0)
    return format_minutes(late_minutes)


def get_check_in_time(obj):
    """Unified check-in formatter"""
    time = obj.get('first_check_in') if isinstance(obj, dict) else getattr(obj, 'check_in_time', None)
    return format_datetime(time)


def get_check_out_time(obj):
    """Unified check-out formatter"""
    time = obj.get('last_check_out') if isinstance(obj, dict) else getattr(obj, 'check_out_time', None)
    return format_datetime(time)



class AttendanceService:

    @staticmethod
    def build_employee_structure(employees, attendance_date):
        data = {}

        for e in employees:
            data[e.user_id] = {
                "id": None,
                "user_id": str(e.user_id),  # Add user_id UUID for edit API
                "employee_name": e.user_name,
                "employee_id": str(e.user_id),  # UUID for backward compatibility
                "custom_employee_id": e.custom_employee_id,  # Add custom_employee_id
                "employee_email": e.user.email,

                "attendance_status": "absent",
                "first_check_in": None,
                "last_check_out": None,
                "first_check_in_time": None,
                "shift_name": None,
                "last_check_out_time": None,

                "total_working_minutes": 0,
                "total_break_minutes": 0,

                "is_late": False,
                "late_minutes": 0,
                "is_early_exit": False,
                "early_exit_minutes": 0,

                "assign_shift": None,
                "last_login_status": None,

                "attendance_date": attendance_date,
                "multiple_entries": [],
                "remarks": None
            }

        return data

    @staticmethod
    def aggregate_records(records, data):
        from WorkLog.models import Attendance
        
        for r in records:
            d = data[r.user_id]

            # Recalculate total_working_minutes if both check_in and check_out are present
            # This ensures data integrity even if stored value is incorrect
            calculated_minutes = 0
            if r.check_in_time and r.check_out_time:
                calculated_minutes = calculate_total_working_minutes(r.check_in_time, r.check_out_time) or 0
                
                # Auto-fix: Update database if stored value differs significantly (more than 1 minute)
                # This fixes incorrect stored values automatically
                stored_minutes = r.total_working_minutes or 0
                if abs(calculated_minutes - stored_minutes) > 1:
                    # Update the stored value in database
                    Attendance.objects.filter(id=r.id).update(total_working_minutes=calculated_minutes)
            elif r.total_working_minutes:
                # Fallback to stored value if calculation not possible
                calculated_minutes = r.total_working_minutes

            d["multiple_entries"].append({
                "id": r.id,
                "check_in_time": format_datetime(r.check_in_time),
                "check_out_time": format_datetime(r.check_out_time),
                "total_working_minutes": calculated_minutes,
                "remarks": r.remarks,
            })
            
            # Track last attendance record (by id) for determining last login status
            if "last_attendance_id" not in d or r.id > d["last_attendance_id"]:
                d["last_attendance_id"] = r.id
                d["last_attendance_record"] = r

            # First check-in
            if r.check_in_time:
                # Handle timezone-aware datetime comparison
                current_checkin = r.check_in_time
                existing_checkin = d["first_check_in_time"]
                # Convert both to naive for comparison if needed
                if current_checkin.tzinfo is not None:
                    current_checkin = current_checkin.replace(tzinfo=None)
                if existing_checkin and existing_checkin.tzinfo is not None:
                    existing_checkin = existing_checkin.replace(tzinfo=None)
                
                if not d["first_check_in_time"] or current_checkin < existing_checkin:
                    d["first_check_in_time"] = r.check_in_time
                    d['shift_name'] = r.assign_shift.shift_name if r.assign_shift else None
                    d["first_check_in"] = r.check_in_time
                    d["attendance_status"] = r.attendance_status
                    d["assign_shift"] = r.assign_shift
                    d["is_late"] = r.is_late
                    d["late_minutes"] = r.late_minutes
                    d["id"] = r.id

            # Last checkout
            if r.check_out_time:
                # Handle timezone-aware datetime comparison
                current_checkout = r.check_out_time
                existing_checkout = d["last_check_out_time"]
                # Convert both to naive for comparison if needed
                if current_checkout.tzinfo is not None:
                    current_checkout = current_checkout.replace(tzinfo=None)
                if existing_checkout and existing_checkout.tzinfo is not None:
                    existing_checkout = existing_checkout.replace(tzinfo=None)
                
                if not d["last_check_out_time"] or current_checkout > existing_checkout:
                    d["last_check_out_time"] = r.check_out_time
                    d["last_check_out"] = r.check_out_time

            # Use recalculated minutes instead of stored value
            d["total_working_minutes"] += calculated_minutes
            d["total_break_minutes"] += (r.break_duration_minutes or 0)

        return data

    @staticmethod
    def finalize_status(data):
        final = []

        for d in data.values():
            # Last login status - based on last attendance record (ordered by -id)
            last_record = d.get("last_attendance_record")
            if last_record:
                # Check the last record to see if it has checkout or only checkin
                if last_record.check_out_time:
                    d["last_login_status"] = "checkout"
                elif last_record.check_in_time:
                    d["last_login_status"] = "checkin"
                else:
                    d["last_login_status"] = None
            else:
                # Fallback to old logic if no records
                if d["last_check_out_time"]:
                    d["last_login_status"] = "checkout"
                elif d["first_check_in_time"]:
                    d["last_login_status"] = "checkin"
                else:
                    d["last_login_status"] = None

            # Time formatting for serializer
            d["check_in"] = (
                format_datetime(d["first_check_in_time"]) if d["first_check_in_time"] else None
            )

            d["shift_name"] = d['shift_name']
            
            d["check_out"] = (
                format_datetime(d["last_check_out_time"]) if d["last_check_out_time"] else None
            )

            d["production_hours"] = format_minutes(d["total_working_minutes"])
            d["break_duration"] = format_minutes(d["total_break_minutes"])
            d["late_minutes_display"] = format_minutes(d["late_minutes"])

            # Early exit
            if d["last_check_out_time"] and d["assign_shift"] and d["assign_shift"].end_time:
                # Handle timezone-aware datetime comparison
                checkout_time = d["last_check_out_time"]
                # Convert to naive datetime if timezone-aware, or keep as-is if naive
                if checkout_time.tzinfo is not None:
                    checkout_time = checkout_time.replace(tzinfo=None)
                
                shift_end_naive = datetime.combine(
                    checkout_time.date(), d["assign_shift"].end_time
                )
                d["is_early_exit"] = checkout_time < shift_end_naive
                d["early_exit_minutes"] = calculate_early_exit_minutes(
                    d["last_check_out_time"],
                    d["assign_shift"].end_time
                )

            d["attendance_date"] = format_date(d["attendance_date"])

            final.append(d)

        return final