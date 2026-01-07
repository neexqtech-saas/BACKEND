"""
Custom DRF JSON Renderer that automatically converts all datetime objects
and datetime strings to the currently active Django timezone in ISO 8601 format.
"""
import re
from datetime import datetime, date
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

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


class TimezoneAwareJSONRenderer(JSONRenderer):
    """
    Custom JSON renderer that recursively converts all datetime objects and strings
    to the active timezone and formats them as ISO 8601 strings.
    """
    
    # Regex patterns for common datetime string formats
    DATETIME_PATTERNS = [
        # "YYYY-MM-DD HH:MM:SS" (most common in this codebase)
        re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'),
        # ISO 8601 without timezone: "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DDTHH:MM:SS.microseconds"
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$'),
        # ISO 8601 with timezone: "YYYY-MM-DDTHH:MM:SS+HH:MM" or "YYYY-MM-DDTHH:MM:SSZ"
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)$'),
    ]
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render data to JSON, converting all datetime objects and strings to timezone-aware ISO 8601 strings.
        """
        if data is None:
            return b''
        
        # Recursively convert datetime objects and strings
        converted_data = self._convert_datetimes(data)
        
        # Use parent class to render to JSON
        return super().render(converted_data, accepted_media_type, renderer_context)
    
    def _is_datetime_string(self, obj):
        """
        Check if a string looks like a datetime string.
        """
        if not isinstance(obj, str):
            return False
        
        # Check against common patterns
        for pattern in self.DATETIME_PATTERNS:
            if pattern.match(obj.strip()):
                return True
        
        return False
    
    def _parse_datetime_string(self, dt_str):
        """
        Parse a datetime string and return a timezone-aware datetime object in UTC.
        Assumes strings without timezone info are in UTC (as stored in database).
        """
        dt_str = dt_str.strip()
        
        # Try parsing "YYYY-MM-DD HH:MM:SS" format (most common)
        try:
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            # Assume UTC (as stored in database)
            return timezone.make_aware(dt, UTC)
        except ValueError:
            pass
        
        # Try parsing ISO 8601 format without timezone
        try:
            # Handle with microseconds
            if '.' in dt_str and 'T' in dt_str:
                dt = datetime.strptime(dt_str.split('+')[0].split('Z')[0], '%Y-%m-%dT%H:%M:%S.%f')
            elif 'T' in dt_str:
                dt = datetime.strptime(dt_str.split('+')[0].split('Z')[0], '%Y-%m-%dT%H:%M:%S')
            else:
                return None
            
            # Assume UTC (as stored in database)
            return timezone.make_aware(dt, UTC)
        except ValueError:
            pass
        
        # Try parsing ISO 8601 with timezone (basic support)
        try:
            # Handle 'Z' suffix (UTC)
            if dt_str.endswith('Z'):
                dt_str_clean = dt_str[:-1]
                if '.' in dt_str_clean:
                    dt = datetime.strptime(dt_str_clean, '%Y-%m-%dT%H:%M:%S.%f')
                else:
                    dt = datetime.strptime(dt_str_clean, '%Y-%m-%dT%H:%M:%S')
                return timezone.make_aware(dt, UTC)
        except ValueError:
            pass
        
        return None
    
    def _convert_datetimes(self, obj):
        """
        Recursively convert datetime objects and datetime strings to timezone-aware ISO 8601 strings.
        Handles dicts, lists, tuples, and nested structures.
        """
        if isinstance(obj, datetime):
            # Convert to active timezone if timezone-aware
            if timezone.is_aware(obj):
                # Convert to currently active timezone
                local_dt = timezone.localtime(obj)
            else:
                # If naive, assume UTC and convert
                utc_dt = timezone.make_aware(obj, UTC)
                local_dt = timezone.localtime(utc_dt)
            
            # Return ISO 8601 formatted string with timezone offset
            return local_dt.isoformat()
        
        elif isinstance(obj, str) and self._is_datetime_string(obj):
            # Parse datetime string (assumed to be in UTC from database)
            dt = self._parse_datetime_string(obj)
            if dt:
                # Convert to currently active timezone
                local_dt = timezone.localtime(dt)
                # Return ISO 8601 formatted string with timezone offset
                return local_dt.isoformat()
            # If parsing fails, return original string
            return obj
        
        elif isinstance(obj, date) and not isinstance(obj, datetime):
            # Handle date objects (not datetime)
            return obj.isoformat()
        
        elif isinstance(obj, dict):
            return {key: self._convert_datetimes(value) for key, value in obj.items()}
        
        elif isinstance(obj, (list, tuple)):
            converted = [self._convert_datetimes(item) for item in obj]
            return tuple(converted) if isinstance(obj, tuple) else converted
        
        else:
            return obj

