def serialize_org_settings(settings, request=None):
    """
    Serialize organization settings using OrganizationSettingsSerializer.
    This ensures consistent response format across all endpoints.
    
    Args:
        settings: OrganizationSettings instance or None
        request: Optional request object for context (needed for organization_logo_url)
    
    Returns:
        dict: Serialized settings data or empty dict if settings is None
    """
    if not settings:
        return {}
    
    from AuthN.serializers import OrganizationSettingsSerializer
    
    context = {'request': request} if request else {}
    serializer = OrganizationSettingsSerializer(settings, context=context)
    return serializer.data