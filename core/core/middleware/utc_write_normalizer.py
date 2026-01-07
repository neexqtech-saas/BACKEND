"""
UTC Write Normalizer Middleware

Intercepts POST/PUT/PATCH requests and converts incoming datetime strings
from local timezone to UTC before they reach serializers/views.

This middleware runs BEFORE timezone activation middleware.
"""
import json
import re
from datetime import datetime
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

# Get UTC timezone - compatible with all Django versions
try:
    import pytz
    UTC = pytz.UTC
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        UTC = ZoneInfo("UTC")
    except ImportError:
        from datetime import timezone as dt_timezone
        UTC = dt_timezone.utc


class UTCWriteNormalizerMiddleware(MiddlewareMixin):
    """
    Middleware that normalizes incoming datetime strings from local timezone to UTC.
    Only processes POST, PUT, PATCH requests with JSON content.
    """
    
    # Regex patterns for ISO 8601 datetime strings
    DATETIME_PATTERNS = [
        # ISO 8601 with timezone: "2025-12-31T21:41:13+05:30" or "2025-12-31T21:41:13Z"
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)$'),
        # ISO 8601 without timezone: "2025-12-31T21:41:13" or "2025-12-31T21:41:13.123456"
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$'),
        # "YYYY-MM-DD HH:MM:SS" format (common in this codebase)
        re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'),
    ]
    
    def process_request(self, request):
        """
        Normalize datetime strings in request body from local timezone to UTC.
        Only processes POST, PUT, PATCH requests with JSON content.
        """
        # Only process write operations
        if request.method not in ('POST', 'PUT', 'PATCH'):
            return None
        
        # Only process JSON requests
        content_type = request.META.get('CONTENT_TYPE', '')
        if 'application/json' not in content_type:
            return None
        
        # Check if request body exists
        if not hasattr(request, '_body') or not request._body:
            return None
        
        try:
            # Parse request body
            body_str = request._body.decode('utf-8')
            if not body_str.strip():
                return None
            
            data = json.loads(body_str)
            
            # Determine user's timezone (same logic as timezone middleware)
            user_tz = self._get_user_timezone(request)
            
            # Recursively convert datetime strings
            converted_data = self._convert_datetime_strings(data, user_tz)
            
            # Re-serialize and update request body
            new_body = json.dumps(converted_data, ensure_ascii=False)
            request._body = new_body.encode('utf-8')
            
            # Update CONTENT_LENGTH header
            request.META['CONTENT_LENGTH'] = str(len(request._body))
            
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            # If parsing fails, leave request unchanged
            pass
        except Exception:
            # On any other error, leave request unchanged
            pass
        
        return None
    
    def _get_user_timezone(self, request):
        """
        Determine user's timezone using same logic as timezone middleware.
        Returns timezone object or UTC as fallback.
        """
        tz_name = "UTC"  # Default fallback
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            
            # Priority 1: Check user.timezone (if field exists)
            if hasattr(user, 'timezone') and user.timezone:
                tz_name = user.timezone
            else:
                # Priority 2: Check organization timezone via UserProfile
                try:
                    if hasattr(user, 'own_user_profile'):
                        user_profile = user.own_user_profile
                        if hasattr(user_profile, 'organization'):
                            org = user_profile.organization
                            if hasattr(org, 'timezone') and org.timezone:
                                tz_name = org.timezone
                except Exception:
                    pass
        
        # Convert timezone name to timezone object
        try:
            try:
                import pytz
                return pytz.timezone(tz_name)
            except ImportError:
                try:
                    from zoneinfo import ZoneInfo
                    return ZoneInfo(tz_name)
                except ImportError:
                    return UTC
        except Exception:
            return UTC
    
    def _is_datetime_string(self, obj):
        """Check if a string looks like a datetime string."""
        if not isinstance(obj, str):
            return False
        
        for pattern in self.DATETIME_PATTERNS:
            if pattern.match(obj.strip()):
                return True
        
        return False
    
    def _parse_datetime_string(self, dt_str, source_tz):
        """
        Parse datetime string and return timezone-aware datetime object in UTC.
        If string has timezone info, uses it; otherwise assumes source_tz.
        """
        dt_str = dt_str.strip()
        
        # Try using dateutil.parser for robust ISO 8601 parsing (if available)
        try:
            from dateutil import parser
            dt = parser.parse(dt_str)
            # If result is naive, make it aware in source_tz
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, source_tz)
            # Convert to UTC
            return dt.astimezone(UTC)
        except (ImportError, ValueError, TypeError):
            pass
        
        # Try parsing ISO 8601 with 'Z' suffix (UTC)
        try:
            if dt_str.endswith('Z'):
                dt_str_clean = dt_str[:-1]
                if '.' in dt_str_clean:
                    dt = datetime.strptime(dt_str_clean, '%Y-%m-%dT%H:%M:%S.%f')
                else:
                    dt = datetime.strptime(dt_str_clean, '%Y-%m-%dT%H:%M:%S')
                return timezone.make_aware(dt, UTC)
        except ValueError:
            pass
        
        # Try parsing ISO 8601 with timezone offset (e.g., +05:30, -05:30)
        try:
            # Use regex to extract datetime and offset
            offset_match = re.search(r'([+-]\d{2}):(\d{2})$', dt_str)
            if offset_match:
                base_str = dt_str[:offset_match.start()]
                offset_sign = -1 if offset_match.group(1)[0] == '-' else 1
                offset_hours = int(offset_match.group(1)[1:]) * offset_sign
                offset_minutes = int(offset_match.group(2)) * offset_sign
                
                # Parse base datetime
                if '.' in base_str:
                    dt = datetime.strptime(base_str, '%Y-%m-%dT%H:%M:%S.%f')
                else:
                    dt = datetime.strptime(base_str, '%Y-%m-%dT%H:%M:%S')
                
                # Calculate offset and create timezone
                from datetime import timedelta, timezone as dt_timezone
                offset_delta = timedelta(hours=offset_hours, minutes=offset_minutes)
                offset_tz = dt_timezone(offset_delta)
                
                # Make aware with offset timezone, then convert to UTC
                dt_aware = dt.replace(tzinfo=offset_tz)
                return dt_aware.astimezone(UTC)
        except (ValueError, AttributeError, IndexError):
            pass
        
        # Try parsing "YYYY-MM-DD HH:MM:SS" format (common in this codebase)
        try:
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            # Make aware in source timezone, then convert to UTC
            dt_aware = timezone.make_aware(dt, source_tz)
            return dt_aware.astimezone(UTC)
        except ValueError:
            pass
        
        # Try parsing ISO 8601 without timezone
        try:
            if 'T' in dt_str:
                # Remove timezone suffix by splitting on + or Z (before any timezone offset)
                # Split on '+' first, then on 'Z', take the first part
                clean_str = dt_str
                if '+' in clean_str:
                    clean_str = clean_str.split('+')[0]
                if 'Z' in clean_str:
                    clean_str = clean_str.split('Z')[0]
                
                # Parse with or without microseconds
                if '.' in clean_str:
                    dt = datetime.strptime(clean_str, '%Y-%m-%dT%H:%M:%S.%f')
                else:
                    dt = datetime.strptime(clean_str, '%Y-%m-%dT%H:%M:%S')
                
                # Make aware in source timezone, then convert to UTC
                dt_aware = timezone.make_aware(dt, source_tz)
                return dt_aware.astimezone(UTC)
        except ValueError:
            pass
        
        return None
    
    def _convert_datetime_strings(self, obj, source_tz):
        """
        Recursively convert datetime strings from source timezone to UTC.
        Returns new object with converted datetime strings.
        """
        if isinstance(obj, str) and self._is_datetime_string(obj):
            # Parse and convert datetime string
            dt = self._parse_datetime_string(obj, source_tz)
            if dt:
                # Return ISO 8601 format in UTC with 'Z' suffix for explicit UTC
                iso_str = dt.isoformat()
                # Ensure UTC is represented with 'Z' suffix (replace +00:00 with Z)
                if iso_str.endswith('+00:00'):
                    iso_str = iso_str[:-6] + 'Z'
                elif '+' in iso_str or iso_str.endswith('-00:00'):
                    # Already has timezone, keep as is
                    pass
                return iso_str
            # If parsing fails, return original string
            return obj
        
        elif isinstance(obj, dict):
            return {key: self._convert_datetime_strings(value, source_tz) for key, value in obj.items()}
        
        elif isinstance(obj, list):
            return [self._convert_datetime_strings(item, source_tz) for item in obj]
        
        else:
            return obj

