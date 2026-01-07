"""
Utility functions for site-based filtering in APIs
"""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from AuthN.models import BaseUserModel
from SiteManagement.models import Site


def validate_admin_and_site(admin_id, site_id):
    """
    Validate admin and site, return admin and site objects
    
    Args:
        admin_id: UUID of admin
        site_id: Required UUID of site
        
    Returns:
        tuple: (admin, site)
        
    Raises:
        Http404: If admin or site not found
    """
    admin = get_object_or_404(BaseUserModel, id=admin_id, role='admin')
    site = get_object_or_404(Site, id=site_id, created_by_admin=admin, is_active=True)
    
    return admin, site


def filter_queryset_by_site(queryset, site_id, site_field='site'):
    """
    Filter queryset by site_id
    
    Args:
        queryset: Django queryset
        site_id: Required UUID of site
        site_field: Name of the site field in the model (default: 'site')
        
    Returns:
        Filtered queryset
    """
    filter_kwargs = {f'{site_field}__id': site_id}
    queryset = queryset.filter(**filter_kwargs)
    return queryset

