"""
Timezone Middleware for automatic timezone activation per request.

Determines timezone based on:
1. request.user.timezone (if exists)
2. request.user.organization.timezone (if exists, via UserProfile)
3. "UTC" as fallback

Activates timezone using django.utils.timezone.activate() for the request lifecycle.
"""
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

try:
    import pytz
    UTC = pytz.UTC
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        pytz = None
        UTC = ZoneInfo("UTC")
    except ImportError:
        pytz = None
        ZoneInfo = None
        # Fallback to datetime.timezone.utc (Python 3.2+)
        from datetime import timezone as dt_timezone
        UTC = dt_timezone.utc


class TimezoneMiddleware(MiddlewareMixin):
    """
    Middleware that activates the appropriate timezone for each request
    based on user or organization settings.
    """
    
    def process_request(self, request):
        """
        Determine and activate timezone for the current request.
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
                    # Check if user has a profile with organization
                    if hasattr(user, 'own_user_profile'):
                        user_profile = user.own_user_profile
                        if hasattr(user_profile, 'organization'):
                            org = user_profile.organization
                            # Check if organization has timezone field
                            if hasattr(org, 'timezone') and org.timezone:
                                tz_name = org.timezone
                except Exception:
                    # Silently fallback to UTC if any error occurs
                    pass
        
        # Validate and get timezone object
        try:
            if pytz:
                tz = pytz.timezone(tz_name)
            elif ZoneInfo:
                tz = ZoneInfo(tz_name)
            else:
                # Fallback: use UTC
                tz = UTC
                tz_name = "UTC"
        except Exception:
            # Fallback to UTC on any error
            tz = UTC
            tz_name = "UTC"
        
        # Activate timezone for this request
        timezone.activate(tz)
        
        # Attach timezone to request for potential use elsewhere
        request.timezone = tz_name
        
        return None
    
    def process_response(self, request, response):
        """
        Deactivate timezone after response is processed.
        """
        timezone.deactivate()
        return response

