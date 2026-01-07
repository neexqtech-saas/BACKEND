from datetime import datetime
from django.utils import timezone

# Get UTC timezone - compatible with all Django versions
try:
    import pytz
    UTC = pytz.UTC
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        UTC = ZoneInfo("UTC")
    except ImportError:
        # Fallback to datetime.timezone.utc (Python 3.2+)
        from datetime import timezone as dt_timezone
        UTC = dt_timezone.utc

from .attendance_utils import *
from .attendance_edit_service import *

class AttendanceEditService:

    @staticmethod
    def update_checkin_checkout(attendance, validated):
        """Main function to update attendance check-in/check-out"""

        check_in = validated.get("check_in_time")
        check_out = validated.get("check_out_time")

        # UPDATE CHECK-IN
        if check_in:
            attendance.check_in_time = check_in
            AttendanceEditService._recalculate_late(attendance)

        # UPDATE CHECK-OUT
        if check_out:
            attendance.check_out_time = check_out

        # RECALCULATE METRICS
        AttendanceEditService._recalculate_full_metrics(attendance)

        # REMARKS UPDATE
        attendance.remarks = f"Updated on {timezone.now().strftime('%Y-%m-%d %I:%M %p')}"
        attendance.save()

        return AttendanceEditService._prepare_response(attendance)

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _recalculate_late(attendance):
        """Recalculate late login"""
        if not attendance.assign_shift or not attendance.check_in_time:
            attendance.is_late = False
            attendance.late_minutes = 0
            return

        shift_start_dt = datetime.combine(
            attendance.attendance_date,
            attendance.assign_shift.start_time
        )
        
        # Make shift_start_dt timezone-aware to match check_in_time
        if timezone.is_aware(attendance.check_in_time):
            # Make shift_start_dt aware using UTC
            shift_start_dt = timezone.make_aware(shift_start_dt, UTC)
            # Both are now timezone-aware, can compare directly
            if attendance.check_in_time > shift_start_dt:
                diff = (attendance.check_in_time - shift_start_dt).total_seconds()
                attendance.late_minutes = int(diff // 60)
                attendance.is_late = True
            else:
                attendance.is_late = False
                attendance.late_minutes = 0
        else:
            # If check_in_time is naive, compare directly (shouldn't happen with USE_TZ=True)
            if attendance.check_in_time > shift_start_dt:
                diff = (attendance.check_in_time - shift_start_dt).total_seconds()
                attendance.late_minutes = int(diff // 60)
                attendance.is_late = True
            else:
                attendance.is_late = False
                attendance.late_minutes = 0

    @staticmethod
    def _recalculate_full_metrics(attendance):
        """Recalculate working, early exit and overtime"""

        ci = attendance.check_in_time
        co = attendance.check_out_time

        if not (ci and co):
            return

        # ▼ REUSE YOUR CLEAN FUNCTION
        attendance.total_working_minutes = calculate_total_working_minutes(ci, co) or 0

        # No shift assigned → no early-exit/overtime
        if not attendance.assign_shift:
            attendance.early_exit_minutes = 0
            attendance.is_early_exit = False
            attendance.overtime_minutes = 0
            return

        shift = attendance.assign_shift

        # ▼ REUSE YOUR FUNCTIONS
        attendance.early_exit_minutes = calculate_early_exit_minutes(
            co, shift.end_time
        )

        attendance.is_early_exit = attendance.early_exit_minutes > 0

        expected_minutes = shift.duration_minutes or (8 * 60)
        attendance.overtime_minutes = calculate_overtime_minutes(
            attendance.total_working_minutes, expected_minutes / 60
        )

    @staticmethod
    def _prepare_response(a):
        """Clean output dict"""

        return {
            "id": a.id,
            "first_check_in": a.check_in_time,
            "last_check_out": a.check_out_time,
            "total_working_minutes": a.total_working_minutes or 0,
            "total_break_minutes": a.break_duration_minutes or 0,
            "is_late": a.is_late,
            "late_minutes": a.late_minutes,
            "attendance_status": a.attendance_status,
            "last_login_status": "checkout" if a.check_out_time else "checkin",
            "user": a.user,
            "assign_shift": a.assign_shift,
            "attendance_date": a.attendance_date,
            "remarks": a.remarks,
        }
