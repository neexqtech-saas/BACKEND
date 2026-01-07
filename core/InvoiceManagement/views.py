"""
Invoice Management API Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
Admin only access
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, date
import json

from .models import Invoice
from .serializers import (
    InvoiceSerializer, InvoiceCreateSerializer, InvoiceUpdateSerializer,
    InvoiceListSerializer
)
from AuthN.models import BaseUserModel, AdminProfile
from SiteManagement.models import Site
from utils.pagination_utils import CustomPagination
from utils.site_filter_utils import filter_queryset_by_site


def get_admin_and_site_optimized(request, site_id):
    """
    Optimized admin and site validation - O(1) queries with select_related
    Returns: (admin, site) tuple or Response with error
    """
    user = request.user
    
    # Fast path for admin role - O(1) query
    if user.role == 'admin':
        admin_id = user.id
        admin = user
        # Single O(1) query with index on (id, created_by_admin, is_active)
        try:
            site = Site.objects.only('id', 'site_name', 'created_by_admin_id', 'is_active').get(
                id=site_id, 
                created_by_admin_id=admin_id, 
                is_active=True
            )
            return admin, site, None
        except Site.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Site not found or you don't have permission to access this site",
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Organization role - O(1) queries with select_related
    elif user.role == 'organization':
        admin_id = request.query_params.get('admin_id')
        if not admin_id:
            return None, None, Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "admin_id is required for organization role. Please provide admin_id as query parameter.",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Single O(1) query with select_related to avoid N+1 - uses index on (id, role)
        try:
            admin = BaseUserModel.objects.select_related('own_admin_profile').only(
                'id', 'role', 'email'
            ).get(id=admin_id, role='admin')
        except BaseUserModel.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        
        # O(1) query - verify admin belongs to organization using select_related
        admin_profile = AdminProfile.objects.select_related('user', 'organization').only(
            'id', 'user_id', 'organization_id'
        ).filter(
            user_id=admin_id,
            organization_id=user.id
        ).first()
        
        if not admin_profile:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Admin does not belong to your organization",
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Single O(1) query with index on (id, created_by_admin, is_active)
        try:
            site = Site.objects.only('id', 'site_name', 'created_by_admin_id', 'is_active').get(
                id=site_id, 
                created_by_admin_id=admin_id, 
                is_active=True
            )
            return admin, site, None
        except Site.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_403_FORBIDDEN,
                "message": "Site not found or you don't have permission to access this site",
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)
    
    else:
        return None, None, Response({
            "status": status.HTTP_403_FORBIDDEN,
            "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
            "data": None
        }, status=status.HTTP_403_FORBIDDEN)


def parse_items_data(data):
    """
    Parse items JSON data from request - handles various input formats
    Returns: list of items or empty list
    """
    if 'items' not in data:
        return []
    
    items_value = data['items']
    
    # Handle case where FormData sends it as a list with one string element
    if isinstance(items_value, list) and len(items_value) > 0:
        if isinstance(items_value[0], str):
            items_value = items_value[0]
    
    if isinstance(items_value, str):
        try:
            parsed = json.loads(items_value)
            if isinstance(parsed, list):
                return parsed
            return []
        except (json.JSONDecodeError, TypeError):
            return []
    elif isinstance(items_value, list):
        return items_value
    else:
        return []


class InvoiceAPIView(APIView):
    """Invoice CRUD - Admin Only - Optimized"""
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request, site_id, pk=None):
        """Get invoice(s) - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            
            if pk:
                # Single O(1) query using index (id, admin) - invoice_id_adm_idx
                invoice = Invoice.objects.filter(
                    id=pk, 
                    admin_id=admin_id
                ).select_related('admin').only(
                    'id', 'admin_id', 'site_id', 'invoice_number', 'invoice_date', 'due_date',
                    'status', 'theme_color', 'business_name', 'client_name', 'total_amount',
                    'created_at', 'updated_at'
                ).first()
                
                if not invoice:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Invoice not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and invoice.site_id != site_id:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Invoice not found for this site"
                    }, status=status.HTTP_404_NOT_FOUND)
                
                serializer = InvoiceSerializer(invoice, context={'request': request})
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Invoice fetched successfully",
                    "data": serializer.data
                })
            else:
                # Get list of invoices - uses index (admin, status) or (admin, invoice_date)
                invoices = Invoice.objects.filter(admin_id=admin_id)
                
                # Filter by site - O(1) with index
                invoices = filter_queryset_by_site(invoices, site_id, 'site')
                
                # Filter by status - uses index (admin, status)
                status_filter = request.query_params.get('status', None)
                if status_filter:
                    invoices = invoices.filter(status=status_filter)
                
                # Optimized date filtering - use date range for index usage
                from_date = request.query_params.get('from_date', None)
                to_date = request.query_params.get('to_date', None)
                
                if from_date:
                    try:
                        from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                        invoices = invoices.filter(invoice_date__gte=from_date_obj)
                    except ValueError:
                        pass  # Invalid date format, ignore
                
                if to_date:
                    try:
                        to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
                        invoices = invoices.filter(invoice_date__lte=to_date_obj)
                    except ValueError:
                        pass  # Invalid date format, ignore
                
                # Search by invoice number or client name - optimized with proper field selection
                search = request.query_params.get('search', None)
                if search:
                    # Uses index on invoice_number for exact matches, icontains for partial
                    invoices = invoices.filter(
                        Q(invoice_number__icontains=search) |
                        Q(client_name__icontains=search)
                    )
                
                # Order by most recent first - uses created_at index
                invoices = invoices.order_by('-created_at')
                
                # Fetch only required fields for list view - reduces data transfer
                invoices = invoices.select_related('admin').only(
                    'id', 'admin_id', 'site_id', 'invoice_number', 'invoice_date', 'due_date',
                    'status', 'client_name', 'total_amount', 'created_at', 'updated_at',
                    'admin__email'
                )
                
                # Pagination - single query with LIMIT/OFFSET using index
                paginator = self.pagination_class()
                paginated_invoices = paginator.paginate_queryset(invoices, request)
                serializer = InvoiceListSerializer(paginated_invoices, many=True)
                
                pagination_data = paginator.get_paginated_response(serializer.data)
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Invoices fetched successfully",
                    "data": serializer.data,  # Array for frontend
                    **pagination_data  # Spread pagination metadata
                })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @transaction.atomic
    def post(self, request, site_id):
        """Create invoice - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            data = request.data.copy()
            
            # Parse items JSON string if it's a string or list containing string
            data['items'] = parse_items_data(data)
            
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)
            
            serializer = InvoiceCreateSerializer(data=data, context={'admin': admin})
            if serializer.is_valid():
                invoice = serializer.save()
                response_serializer = InvoiceSerializer(invoice, context={'request': request})
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Invoice created successfully",
                    "data": response_serializer.data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @transaction.atomic
    def put(self, request, site_id, pk):
        """Update invoice - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index invoice_id_adm_idx
            invoice = Invoice.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not invoice:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Invoice not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and invoice.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Invoice not found for this site"
                }, status=status.HTTP_404_NOT_FOUND)
            
            data = request.data.copy()
            
            # Parse items JSON string if it's a string or list containing string
            data['items'] = parse_items_data(data)
            
            serializer = InvoiceUpdateSerializer(invoice, data=data, partial=True)
            if serializer.is_valid():
                invoice = serializer.save()
                response_serializer = InvoiceSerializer(invoice, context={'request': request})
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Invoice updated successfully",
                    "data": response_serializer.data
                })
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, site_id, pk=None):
        """Delete invoice - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            # Single O(1) query using index invoice_id_adm_idx
            invoice = Invoice.objects.filter(
                id=pk, 
                admin_id=admin.id
            ).only('id', 'site_id').first()
            
            if not invoice:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Invoice not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and invoice.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Invoice not found for this site"
                }, status=status.HTTP_404_NOT_FOUND)
            
            invoice.delete()
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Invoice deleted successfully",
                "data": None
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
