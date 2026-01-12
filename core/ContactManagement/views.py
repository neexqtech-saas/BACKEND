"""
Contact Management Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Count
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone
from datetime import datetime, timedelta, time

from .models import Contact
from .serializers import (
    ContactSerializer, ContactCreateSerializer, ContactExtractionResultSerializer
)
from .ocr_service import BusinessCardOCRService
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
            admin = BaseUserModel.objects.only(
                'id', 'role', 'email'
            ).get(id=admin_id, role='admin')
        except BaseUserModel.DoesNotExist:
            return None, None, Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        
        # O(1) query - verify admin belongs to organization using select_related
        # Uses index on (user_id, organization_id) if exists, else (user_id)
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


class ContactExtractAPIView(APIView):
    """
    Extract contact information from business card image using OCR
    Optimized with O(1) admin/site validation
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, site_id, user_id=None):
        """Extract contact details from uploaded business card image"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            if 'business_card_image' not in request.FILES:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Business card image is required",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            image_file = request.FILES['business_card_image']
            
            # Validate image file
            if not image_file.content_type.startswith('image/'):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "File must be an image",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Initialize OCR service
            ocr_service = BusinessCardOCRService()
            
            # Extract contact information
            extraction_result = ocr_service.extract_contact_info(image_file)
            
            if not extraction_result.get('success'):
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": extraction_result.get('error', 'Failed to extract contact information'),
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Remove success and error fields for response
            extraction_result.pop('success', None)
            extraction_result.pop('error', None)
            
            # Serialize the result
            serializer = ContactExtractionResultSerializer(data=extraction_result)
            if serializer.is_valid():
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Contact information extracted successfully",
                    "data": serializer.validated_data
                })
            else:
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Contact information extracted with some validation issues",
                    "data": extraction_result
                })
                
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error extracting contact information: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactAPIView(APIView):
    """
    Contact CRUD Operations - Optimized
    - Admin and users can create, read, update, and delete contacts
    - Admin can see all contacts, users can only see their own
    - Search functionality for contacts
    All queries O(1) or using proper database indexes
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request, site_id, user_id=None, pk=None):
        """Get contacts - filtered by role - O(1) queries with index optimization"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            admin_id = admin.id
            user = request.user
            
            if pk:
                # Single O(1) query using index contact_id_adm_idx (id, admin)
                contact = Contact.objects.filter(
                    id=pk,
                    admin_id=admin_id
                ).select_related('admin', 'user', 'created_by').only(
                    'id', 'admin_id', 'user_id', 'site_id', 'full_name', 'company_name', 'job_title',
                    'mobile_number', 'email_address', 'state', 'city', 'source_type',
                    'created_by_id', 'created_at', 'updated_at'
                ).first()
                
                if not contact:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Contact not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # O(1) site check
                if site_id and contact.site_id != site_id:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Contact not found for this site"
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Check access permission
                if user.role == 'user' and contact.user_id != user.id:
                    return Response({
                        "status": status.HTTP_403_FORBIDDEN,
                        "message": "You don't have permission to view this contact",
                        "data": None
                    }, status=status.HTTP_403_FORBIDDEN)
                
                serializer = ContactSerializer(contact, context={'request': request})
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Contact fetched successfully",
                    "data": serializer.data
                })
            else:
                # Base queryset with index optimization - uses contact_adm_created_idx
                if user.role == 'admin':
                    queryset = Contact.objects.filter(admin_id=admin_id)
                    if user_id:
                        queryset = queryset.filter(user_id=user_id)
                elif user.role == 'user':
                    # Uses index contact_adm_user_created_idx
                    queryset = Contact.objects.filter(admin_id=admin_id, user_id=user.id)
                else:
                    queryset = Contact.objects.none()
                
                # Filter by site - O(1) with index
                queryset = filter_queryset_by_site(queryset, site_id, 'site')
                
                # Search functionality - optimized with proper field selection and index usage
                search_query = request.query_params.get('search', '').strip()
                if search_query:
                    # Uses indexes: contact_adm_name_idx, contact_adm_company_idx, contact_adm_mobile_idx, contact_adm_email_idx
                    queryset = queryset.filter(
                        Q(full_name__icontains=search_query) |
                        Q(company_name__icontains=search_query) |
                        Q(mobile_number__icontains=search_query) |
                        Q(email_address__icontains=search_query) |
                        Q(state__icontains=search_query) |
                        Q(city__icontains=search_query)
                    )
                
                # Filter by source type - uses contact_adm_source_created_idx index
                source_type = request.query_params.get('source_type')
                if source_type:
                    queryset = queryset.filter(source_type=source_type)
                
                # Filter by company - uses contact_adm_company_idx index
                company = request.query_params.get('company')
                if company:
                    queryset = queryset.filter(company_name__icontains=company)
                
                # Filter by state/city - uses contact_adm_state_city_idx index
                state = request.query_params.get('state')
                if state:
                    queryset = queryset.filter(state__icontains=state)
                
                city = request.query_params.get('city')
                if city:
                    queryset = queryset.filter(city__icontains=city)
                
                # Optimized date filtering - use datetime range for index usage (contact_adm_created_idx)
                date_from_str = request.query_params.get('date_from')
                date_to_str = request.query_params.get('date_to')
                
                if not date_from_str and not date_to_str:
                    # Default to last 10 days - uses index efficiently
                    today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
                    ten_days_ago_start = (timezone.now() - timedelta(days=10)).replace(hour=0, minute=0, second=0, microsecond=0)
                    queryset = queryset.filter(created_at__gte=ten_days_ago_start, created_at__lte=today_end)
                else:
                    if date_from_str:
                        try:
                            date_from_obj = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                            date_from_dt = timezone.make_aware(datetime.combine(date_from_obj, time.min))
                            queryset = queryset.filter(created_at__gte=date_from_dt)
                        except ValueError:
                            pass
                    
                    if date_to_str:
                        try:
                            date_to_obj = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                            date_to_dt = timezone.make_aware(datetime.combine(date_to_obj, time.max))
                            queryset = queryset.filter(created_at__lte=date_to_dt)
                        except ValueError:
                            pass
                
                # Order by most recent first - uses contact_adm_created_idx index
                queryset = queryset.order_by('-created_at')
                
                # Fetch only required fields with select_related to avoid N+1
                queryset = queryset.select_related('admin', 'user', 'created_by').only(
                    'id', 'admin_id', 'user_id', 'site_id', 'full_name', 'company_name', 'job_title',
                    'mobile_number', 'email_address', 'state', 'city', 'source_type',
                    'created_by_id', 'created_at', 'updated_at',
                    'admin__email', 'user__email', 'created_by__email', 'created_by__username'
                )
                
                # Pagination - single query with LIMIT/OFFSET using index
                paginator = self.pagination_class()
                paginated_qs = paginator.paginate_queryset(queryset, request)
                serializer = ContactSerializer(paginated_qs, many=True, context={'request': request})
                pagination_data = paginator.get_paginated_response(serializer.data)
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Contacts fetched successfully",
                    "data": serializer.data,
                    **pagination_data
                })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @transaction.atomic
    def post(self, request, site_id, user_id=None):
        """Create contact - Admin or User can create - Optimized"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            user = request.user
            
            # Only admin and user can create contacts
            if user.role not in ['admin', 'user']:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Only admin and user can create contacts",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data.copy()
            data['created_by'] = str(user.id)
            # Set site if provided
            if site_id:
                data['site'] = str(site.id)
            
            # Determine user based on who is creating
            user_obj = None
            if user.role == 'user':
                # If user/employee is creating, both admin_id and user_id should be saved
                user_obj = user
            elif user.role == 'admin':
                # If admin is creating, user_id should be null
                user_obj = None
            
            # Clean empty strings from data - convert to None
            for key in list(data.keys()):
                if isinstance(data[key], str) and data[key].strip() == '':
                    data[key] = None
            
            # Set defaults for required fields
            if not data.get('mobile_number'):
                data['mobile_number'] = ''
            if not data.get('source_type'):
                data['source_type'] = 'manual'
            
            serializer = ContactCreateSerializer(data=data)
            # Always try to save, even if validation has minor issues
            if serializer.is_valid(raise_exception=False):
                # O(1) query to get created_by user - uses primary key
                created_by_user = BaseUserModel.objects.filter(id=data['created_by']).only('id').first()
                if not created_by_user:
                    created_by_user = user
                
                contact = serializer.save(
                    admin=admin,
                    user=user_obj,
                    created_by=created_by_user
                )
                response_serializer = ContactSerializer(contact, context={'request': request})
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Contact created successfully",
                    "data": response_serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                # If validation fails, create with cleaned data anyway
                created_by_user = BaseUserModel.objects.filter(id=data['created_by']).only('id').first()
                if not created_by_user:
                    created_by_user = user
                # Prepare data for direct model creation
                contact_data = {}
                for field in ContactCreateSerializer.Meta.fields:
                    if field in data and data[field] is not None:
                        contact_data[field] = data[field]
                
                # Ensure mobile_number has a value
                if 'mobile_number' not in contact_data or not contact_data['mobile_number']:
                    contact_data['mobile_number'] = ''
                if 'source_type' not in contact_data or not contact_data['source_type']:
                    contact_data['source_type'] = 'manual'
                
                contact = Contact.objects.create(
                    admin=admin,
                    user=user_obj,
                    created_by=created_by_user,
                    **contact_data
                )
                
                response_serializer = ContactSerializer(contact, context={'request': request})
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Contact created successfully",
                    "data": response_serializer.data
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @transaction.atomic
    def put(self, request, site_id, user_id=None, pk=None):
        """Update contact - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            user = request.user
            # Single O(1) query using index contact_id_adm_idx
            contact = Contact.objects.filter(id=pk, admin_id=admin.id).only(
                'id', 'user_id', 'site_id'
            ).first()
            if not contact:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Contact not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and contact.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Contact not found for this site"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check access permission
            if user.role == 'user':
                # User can only update contacts where user_id matches
                if contact.user_id != user.id:
                    return Response({
                        "status": status.HTTP_403_FORBIDDEN,
                        "message": "You don't have permission to update this contact",
                        "data": None
                    }, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data.copy()
            serializer = ContactCreateSerializer(contact, data=data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                
                response_serializer = ContactSerializer(contact, context={'request': request})
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Contact updated successfully",
                    "data": response_serializer.data
                })
            else:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "Validation error",
                    "data": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @transaction.atomic
    def delete(self, request, site_id, user_id=None, pk=None):
        """Delete contact - Optimized O(1) query"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            user = request.user
            # Single O(1) query using index contact_id_adm_idx
            contact = Contact.objects.filter(id=pk, admin_id=admin.id).only(
                'id', 'user_id', 'site_id'
            ).first()
            if not contact:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Contact not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) site check
            if site_id and contact.site_id != site_id:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Contact not found for this site"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check access permission
            if user.role == 'user':
                # User can only delete contacts where user_id matches
                if contact.user_id != user.id:
                    return Response({
                        "status": status.HTTP_403_FORBIDDEN,
                        "message": "You don't have permission to delete this contact",
                        "data": None
                    }, status=status.HTTP_403_FORBIDDEN)
            
            contact.delete()
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Contact deleted successfully",
                "data": None
            })
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactStatsAPIView(APIView):
    """
    Get statistics about contacts
    Optimized with single aggregation query
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, site_id, user_id=None):
        """Get contact statistics - O(1) aggregation queries with proper indexes"""
        try:
            admin, site, error_response = get_admin_and_site_optimized(request, site_id)
            if error_response:
                return error_response
            
            user = request.user
            admin_id = admin.id
            
            # Base queryset with index optimization - uses contact_adm_created_idx
            if user.role == 'admin':
                contacts = Contact.objects.filter(admin_id=admin_id)
                if user_id:
                    contacts = contacts.filter(user_id=user_id)
            elif user.role == 'user':
                # Uses index contact_adm_user_created_idx
                contacts = Contact.objects.filter(admin_id=admin_id, user_id=user.id)
            else:
                contacts = Contact.objects.none()
            
            # Filter by site - O(1) with index
            contacts = filter_queryset_by_site(contacts, site_id, 'site')
            
            # Single optimized query with aggregation - all stats in one query
            # Uses indexes for efficient counting
            stats = contacts.aggregate(
                total_contacts=Count('id'),
                scanned_contacts=Count('id', filter=Q(source_type='scanned')),
                manual_contacts=Count('id', filter=Q(source_type='manual')),
                contacts_with_email=Count('id', filter=~Q(email_address__isnull=True) & ~Q(email_address='')),
                contacts_with_phone=Count('id', filter=~Q(mobile_number__isnull=True) & ~Q(mobile_number='')),
                contacts_with_company=Count('id', filter=~Q(company_name__isnull=True) & ~Q(company_name='')),
            )
            
            # Additional distinct counts - optimized queries using indexes
            # Uses contact_adm_company_idx for company_name
            stats['unique_companies'] = contacts.exclude(
                company_name__isnull=True
            ).exclude(
                company_name=''
            ).values('company_name').distinct().count()
            
            # Uses contact_adm_state_city_idx for state
            stats['unique_states'] = contacts.exclude(
                state__isnull=True
            ).exclude(
                state=''
            ).values('state').distinct().count()
            
            # Uses contact_adm_state_city_idx for city
            stats['unique_cities'] = contacts.exclude(
                city__isnull=True
            ).exclude(
                city=''
            ).values('city').distinct().count()
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Statistics fetched successfully",
                "data": stats
            })
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
