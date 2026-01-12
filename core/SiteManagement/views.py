"""
Site Management Views
Optimized for high-traffic, low-cost, future-proof architecture
All queries O(1) or using proper database indexes
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Min, Max, Q
from django.utils import timezone
from django.http import JsonResponse

from .models import Site, EmployeeAdminSiteAssignment
from .serializers import (
    SiteSerializer, SiteCreateUpdateSerializer,
    EmployeeAdminSiteAssignmentSerializer,
    EmployeeAdminSiteAssignmentCreateSerializer,
    EmployeeAdminSiteAssignmentUpdateSerializer
)
from AuthN.models import BaseUserModel, AdminProfile, UserProfile
from utils.Employee.assignment_utils import get_employees_assigned_to_site


class SiteAPIView(APIView):
    """
    Site CRUD Operations - Optimized
    GET: /api/sites/{admin_id} - List sites for admin
    GET: /api/sites/{admin_id}/{site_id} - Get site details
    POST: /api/sites/{admin_id} - Create site
    PUT: /api/sites/{admin_id}/{site_id} - Update site
    DELETE: /api/sites/{admin_id}/{site_id} - Delete/deactivate site
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, admin_id, site_id=None):
        """Get all sites for admin or specific site details - O(1) queries"""
        try:
            # O(1) query - Validate admin using index on (id, role)
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            
            # If site_id is provided, return specific site details
            if site_id:
                # O(1) query using index site_id_admin_idx (id, created_by_admin)
                # Include created_by_admin__own_admin_profile for serializer access
                site = Site.objects.select_related(
                    'organization', 
                    'created_by_admin',
                    'created_by_admin__own_admin_profile'
                ).filter(
                    id=site_id, 
                    created_by_admin=admin
                ).only(
                    'id', 'organization_id', 'created_by_admin_id', 'site_name', 
                    'address', 'city', 'state', 'pincode', 'contact_person', 
                    'contact_number', 'description', 'is_active', 'created_at', 'updated_at'
                ).first()
                
                if not site:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Site not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                serializer = SiteSerializer(site)
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Site retrieved successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            
            # Otherwise, return all sites for admin - O(1) query using index site_admin_active_idx
            # Include created_by_admin__own_admin_profile for serializer access
            sites = Site.objects.filter(
                created_by_admin=admin, 
                is_active=True
            ).select_related(
                'organization', 
                'created_by_admin',
                'created_by_admin__own_admin_profile'
            ).only(
                'id', 'organization_id', 'created_by_admin_id', 'site_name', 
                'address', 'city', 'state', 'pincode', 'contact_person', 
                'contact_number', 'description', 'is_active', 'created_at', 'updated_at'
            ).order_by('site_name')
            
            serializer = SiteSerializer(sites, many=True)
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Sites retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
                
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving sites: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def post(self, request, admin_id):
        """Create site - Optimized"""
        try:
            # O(1) query - Validate admin
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            
            # O(1) query - Get admin profile with select_related
            admin_profile = AdminProfile.objects.select_related('organization').filter(
                user=admin
            ).only('id', 'user_id', 'organization_id').first()
            
            if not admin_profile:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Admin profile not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = SiteCreateUpdateSerializer(
                data=request.data,
                context={'admin_id': admin_id}
            )
            
            if serializer.is_valid():
                # Set organization and admin from validated data or context
                validated_data = serializer.validated_data
                validated_data['organization'] = admin_profile.organization
                validated_data['created_by_admin'] = admin
                site = serializer.save()
                
                # Create default resources for the site
                from .utils import create_default_site_resources
                create_default_site_resources(admin=admin, site=site)
                
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Site created successfully",
                    "data": SiteSerializer(site).data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error creating site: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def put(self, request, admin_id, site_id):
        """Update site - Optimized O(1) query"""
        try:
            # O(1) query - Validate admin
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            
            # O(1) query using index site_id_admin_idx
            # Fetch all fields needed for serializer
            site = Site.objects.filter(
                id=site_id, 
                created_by_admin=admin
            ).select_related('organization', 'created_by_admin').only(
                'id', 'organization_id', 'created_by_admin_id', 'site_name',
                'address', 'city', 'state', 'pincode', 'contact_person',
                'contact_number', 'description', 'is_active', 'created_at', 'updated_at'
            ).first()
            
            if not site:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Site not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = SiteCreateUpdateSerializer(
                site,
                data=request.data,
                partial=True,
                context={'admin_id': admin_id}
            )
            
            if serializer.is_valid():
                serializer.save()
                # Refresh site object to get updated data
                site.refresh_from_db()
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Site updated successfully",
                    "data": SiteSerializer(site).data
                }, status=status.HTTP_200_OK)
            
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error updating site: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def delete(self, request, admin_id, site_id):
        """Delete/deactivate site - Optimized O(1) update"""
        try:
            # O(1) query - Validate admin
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            
            # O(1) query using index site_id_admin_idx
            site = Site.objects.filter(
                id=site_id, 
                created_by_admin=admin
            ).only('id').first()
            
            if not site:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Site not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # O(1) optimized update - only update is_active field using index
            Site.objects.filter(id=site_id, created_by_admin=admin).update(is_active=False)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Site deactivated successfully",
                "data": None
            }, status=status.HTTP_200_OK)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error deactivating site: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeAssignmentAPIView(APIView):
    """
    Employee Assignment CRUD Operations - Optimized
    GET: /api/employee-assignments/{admin_id} - List all assignments under admin
    GET: /api/employee-assignments/{admin_id}/{employee_id} - Get employee assignments
    POST: /api/employee-assignments/{admin_id}/{employee_id} - Create assignment
    PUT: /api/employee-assignments/{admin_id}/{employee_id}/{assignment_id} - Update assignment
    DELETE: /api/employee-assignments/{admin_id}/{employee_id}/{assignment_id} - End assignment
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, admin_id, employee_id=None, assignment_id=None):
        """Get assignments - Optimized"""
        try:
            # O(1) query - Validate admin
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            
            if assignment_id and employee_id:
                # Get single assignment - O(1) query
                assignment = EmployeeAdminSiteAssignment.objects.filter(
                    id=assignment_id,
                    admin=admin,
                    employee_id=employee_id
                ).select_related('employee', 'admin', 'admin__own_admin_profile', 'site', 'assigned_by').only(
                    'id', 'employee_id', 'admin_id', 'site_id', 'start_date', 
                    'end_date', 'is_active', 'assigned_by_id', 'assignment_reason', 
                    'created_at', 'updated_at'
                ).first()
                
                if not assignment:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Assignment not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
                
                serializer = EmployeeAdminSiteAssignmentSerializer(assignment)
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Assignment retrieved successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            elif employee_id:
                # Get all assignments for employee - Optimized with proper indexes
                active_only = request.query_params.get('active_only', 'false').lower() == 'true'
                admin_only = request.query_params.get('admin_only', 'false').lower() == 'true'
                
                filter_kwargs = {
                    'employee_id': employee_id
                }
                
                if admin_only:
                    filter_kwargs['admin'] = admin
                
                if active_only:
                    filter_kwargs['is_active'] = True
                
                # O(1) query using index assignment_emp_dates_idx or assignment_emp_active_idx
                assignments = EmployeeAdminSiteAssignment.objects.filter(
                    **filter_kwargs
                ).select_related(
                    'employee', 'employee__own_user_profile', 
                    'admin', 'admin__own_admin_profile', 
                    'site', 'assigned_by'
                ).only(
                    'id', 'employee_id', 'admin_id', 'site_id', 'start_date', 
                    'end_date', 'is_active', 'assigned_by_id', 'assignment_reason', 
                    'created_at', 'updated_at'
                ).order_by('-start_date', '-created_at')
                
                serializer = EmployeeAdminSiteAssignmentSerializer(assignments, many=True)
                
                # Optimized count queries - single aggregation
                all_assignments_qs = EmployeeAdminSiteAssignment.objects.filter(employee_id=employee_id)
                active_count = all_assignments_qs.filter(is_active=True).count()
                history_count = all_assignments_qs.filter(is_active=False).count()
                
                # Optimized admin summary - use values() for efficient grouping
                admin_summary_data = all_assignments_qs.values('admin_id').annotate(
                    total=Count('id'),
                    active=Count('id', filter=Q(is_active=True)),
                    history=Count('id', filter=Q(is_active=False)),
                    first_date=Min('start_date'),
                    last_date=Max('end_date')
                )
                
                admin_summary = []
                for item in admin_summary_data:
                    # Fetch admin without select_related first to avoid deferral conflict
                    admin_obj = BaseUserModel.objects.only('id', 'email').get(id=item['admin_id'])
                    
                    # Then fetch admin_profile separately if needed
                    admin_name = None
                    try:
                        admin_profile = AdminProfile.objects.only('admin_name').get(user=admin_obj)
                        admin_name = admin_profile.admin_name
                    except AdminProfile.DoesNotExist:
                        pass
                    
                    admin_summary.append({
                        'admin_id': str(item['admin_id']),
                        'admin_name': admin_name or admin_obj.email,
                        'admin_email': admin_obj.email,
                        'total_assignments': item['total'],
                        'active_assignments': item['active'],
                        'history_assignments': item['history'],
                        'first_assignment_date': item['first_date'],
                        'last_assignment_date': item['last_date']
                    })
                
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": f"Assignments retrieved successfully ({'active only' if active_only else 'including history'}{', all admins' if not admin_only else ''})",
                    "data": serializer.data,
                    "summary": {
                        "total": len(serializer.data),
                        "active_count": active_count,
                        "history_count": history_count,
                        "admin_summary": admin_summary
                    }
                }, status=status.HTTP_200_OK)
            else:
                # Get all assignments under admin - O(1) query using index assignment_admin_active_idx
                assignments = EmployeeAdminSiteAssignment.objects.filter(
                    admin=admin
                ).select_related(
                    'employee', 'employee__own_user_profile', 
                    'admin', 'site', 'assigned_by'
                ).only(
                    'id', 'employee_id', 'admin_id', 'site_id', 'start_date', 
                    'end_date', 'is_active', 'assigned_by_id', 'assignment_reason', 
                    'created_at', 'updated_at'
                ).order_by('-start_date')
                
                serializer = EmployeeAdminSiteAssignmentSerializer(assignments, many=True)
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Assignments retrieved successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
                
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving assignments: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def post(self, request, admin_id, employee_id):
        """Create assignment - Optimized"""
        try:
            # O(1) queries - Validate admin and employee
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            employee = BaseUserModel.objects.only('id', 'role').get(id=employee_id, role='user')
            
            serializer = EmployeeAdminSiteAssignmentCreateSerializer(
                data=request.data,
                context={
                    'employee': employee,
                    'assigned_by': request.user if request.user.is_authenticated else None
                }
            )
            
            if serializer.is_valid():
                # Ensure admin matches
                if serializer.validated_data.get('admin') != admin:
                    return Response({
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "Admin mismatch",
                        "data": None
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                assignment = serializer.save()
                return Response({
                    "status": status.HTTP_201_CREATED,
                    "message": "Assignment created successfully",
                    "data": EmployeeAdminSiteAssignmentSerializer(assignment).data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin or employee not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error creating assignment: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def put(self, request, admin_id, employee_id, assignment_id):
        """Update assignment - Optimized O(1) query"""
        try:
            # O(1) queries - Validate admin and employee
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            employee = BaseUserModel.objects.only('id', 'role').get(id=employee_id, role='user')
            
            # O(1) query
            assignment = EmployeeAdminSiteAssignment.objects.filter(
                id=assignment_id,
                admin=admin,
                employee=employee
            ).only('id').first()
            
            if not assignment:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Assignment not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = EmployeeAdminSiteAssignmentUpdateSerializer(
                assignment,
                data=request.data,
                partial=True
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Assignment updated successfully",
                    "data": EmployeeAdminSiteAssignmentSerializer(assignment).data
                }, status=status.HTTP_200_OK)
            
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin or employee not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error updating assignment: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @transaction.atomic
    def delete(self, request, admin_id, employee_id, assignment_id):
        """End assignment - Optimized"""
        try:
            # O(1) queries - Validate admin and employee
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            employee = BaseUserModel.objects.only('id', 'role').get(id=employee_id, role='user')
            
            # O(1) query
            assignment = EmployeeAdminSiteAssignment.objects.filter(
                id=assignment_id,
                admin=admin,
                employee=employee
            ).only('id').first()
            
            if not assignment:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Assignment not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # End assignment by setting end_date and is_active=False
            end_date = request.data.get('end_date', timezone.now().date())
            assignment.end_assignment(end_date=end_date)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Assignment ended successfully",
                "data": None
            }, status=status.HTTP_200_OK)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin or employee not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error ending assignment: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeAdminsReportAPIView(APIView):
    """
    Reporting API: Get all admins for an employee - Optimized
    GET: /api/reports/employee-admins/{employee_id}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        """Get all admins for employee - Optimized"""
        try:
            # O(1) query - Validate employee
            employee = BaseUserModel.objects.only('id', 'role').get(id=employee_id, role='user')
            
            # O(1) query using index assignment_emp_dates_idx
            assignments = EmployeeAdminSiteAssignment.objects.filter(
                employee=employee
            ).select_related(
                'admin', 'admin__own_admin_profile', 'site'
            ).only(
                'id', 'admin_id', 'site_id', 'start_date', 'end_date', 
                'is_active', 'assignment_reason'
            ).order_by('-start_date')
            
            result = []
            for assignment in assignments:
                admin_name = None
                if hasattr(assignment.admin, 'own_admin_profile'):
                    admin_name = assignment.admin.own_admin_profile.admin_name
                
                result.append({
                    'assignment_id': assignment.id,
                    'admin_id': str(assignment.admin.id),
                    'admin_name': admin_name,
                    'admin_email': assignment.admin.email,
                    'site_id': assignment.site.id if assignment.site else None,
                    'site_name': assignment.site.site_name if assignment.site else None,
                    'start_date': assignment.start_date,
                    'end_date': assignment.end_date,
                    'is_active': assignment.is_active,
                    'assignment_reason': assignment.assignment_reason
                })
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Employee admins retrieved successfully",
                "data": result
            }, status=status.HTTP_200_OK)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Employee not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving employee admins: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminEmployeesReportAPIView(APIView):
    """
    Reporting API: Get all employees under an admin - Optimized
    GET: /api/reports/admin-employees/{admin_id}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, admin_id):
        """Get all employees under admin - Optimized"""
        try:
            # O(1) query - Validate admin
            admin = BaseUserModel.objects.only('id', 'role').get(id=admin_id, role='admin')
            
            # O(1) query using index assignment_admin_active_idx
            assignments = EmployeeAdminSiteAssignment.objects.filter(
                admin=admin
            ).select_related(
                'employee', 'employee__own_user_profile', 'site'
            ).only(
                'id', 'employee_id', 'site_id', 'start_date', 'end_date', 
                'is_active', 'assignment_reason',
                'site__id', 'site__site_name'  # Include site fields needed
            ).order_by('-start_date')
            
            result = []
            for assignment in assignments:
                employee_name = None
                if hasattr(assignment.employee, 'own_user_profile'):
                    employee_name = assignment.employee.own_user_profile.user_name
                
                result.append({
                    'assignment_id': assignment.id,
                    'employee_id': str(assignment.employee.id),
                    'employee_name': employee_name,
                    'employee_email': assignment.employee.email,
                    'site_id': assignment.site.id if assignment.site else None,
                    'site_name': assignment.site.site_name if assignment.site else None,
                    'start_date': assignment.start_date,
                    'end_date': assignment.end_date,
                    'is_active': assignment.is_active,
                    'assignment_reason': assignment.assignment_reason
                })
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Admin employees retrieved successfully",
                "data": result
            }, status=status.HTTP_200_OK)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Admin not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving admin employees: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SiteAssignmentsReportAPIView(APIView):
    """
    Reporting API: Get site assignments with date ranges - Optimized
    GET: /api/reports/site-assignments/{site_id}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        """Get site assignments with date ranges - Optimized"""
        try:
            # O(1) query - Validate site (fetch site_name in case it's needed)
            site = Site.objects.only('id', 'site_name').get(id=site_id)
            
            # O(1) query using index assignment_site_dates_idx
            assignments = EmployeeAdminSiteAssignment.objects.filter(
                site=site
            ).select_related(
                'employee', 'employee__own_user_profile', 
                'admin', 'admin__own_admin_profile'
            ).only(
                'id', 'employee_id', 'admin_id', 'start_date', 'end_date', 
                'is_active', 'assignment_reason'
            ).order_by('-start_date')
            
            result = []
            for assignment in assignments:
                employee_name = None
                if hasattr(assignment.employee, 'own_user_profile'):
                    employee_name = assignment.employee.own_user_profile.user_name
                
                admin_name = None
                if hasattr(assignment.admin, 'own_admin_profile'):
                    admin_name = assignment.admin.own_admin_profile.admin_name
                
                result.append({
                    'assignment_id': assignment.id,
                    'employee_id': str(assignment.employee.id),
                    'employee_name': employee_name,
                    'employee_email': assignment.employee.email,
                    'admin_id': str(assignment.admin.id),
                    'admin_name': admin_name,
                    'admin_email': assignment.admin.email,
                    'start_date': assignment.start_date,
                    'end_date': assignment.end_date,
                    'is_active': assignment.is_active,
                    'assignment_reason': assignment.assignment_reason
                })
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Site assignments retrieved successfully",
                "data": result
            }, status=status.HTTP_200_OK)
            
        except Site.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Site not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving site assignments: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeHistoryReportAPIView(APIView):
    """
    Reporting API: Get complete assignment history for an employee - Optimized
    GET: /api/reports/employee-history/{employee_id}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        """Get complete assignment history for employee - Optimized"""
        try:
            # O(1) query - Validate employee
            employee = BaseUserModel.objects.only('id', 'role').get(id=employee_id, role='user')
            
            # O(1) query using index assignment_emp_dates_idx
            assignments = EmployeeAdminSiteAssignment.objects.filter(
                employee=employee
            ).select_related(
                'admin', 'admin__own_admin_profile', 
                'site', 'assigned_by', 'assigned_by__own_admin_profile', 
                'assigned_by__own_organization_profile'
            ).only(
                'id', 'admin_id', 'site_id', 'assigned_by_id', 'start_date', 
                'end_date', 'is_active', 'assignment_reason', 'created_at', 'updated_at',
                'site__id', 'site__site_name'  # Include site fields needed
            ).order_by('-start_date')
            
            result = []
            for assignment in assignments:
                admin_name = None
                if hasattr(assignment.admin, 'own_admin_profile'):
                    admin_name = assignment.admin.own_admin_profile.admin_name
                
                assigned_by_name = None
                if assignment.assigned_by:
                    if assignment.assigned_by.role == 'admin' and hasattr(assignment.assigned_by, 'own_admin_profile'):
                        assigned_by_name = assignment.assigned_by.own_admin_profile.admin_name
                    elif assignment.assigned_by.role == 'organization' and hasattr(assignment.assigned_by, 'own_organization_profile'):
                        assigned_by_name = assignment.assigned_by.own_organization_profile.organization_name
                
                result.append({
                    'assignment_id': assignment.id,
                    'admin_id': str(assignment.admin.id),
                    'admin_name': admin_name,
                    'admin_email': assignment.admin.email,
                    'site_id': assignment.site.id if assignment.site else None,
                    'site_name': assignment.site.site_name if assignment.site else None,
                    'start_date': assignment.start_date,
                    'end_date': assignment.end_date,
                    'is_active': assignment.is_active,
                    'assigned_by_id': str(assignment.assigned_by.id) if assignment.assigned_by else None,
                    'assigned_by_name': assigned_by_name,
                    'assignment_reason': assignment.assignment_reason,
                    'created_at': assignment.created_at,
                    'updated_at': assignment.updated_at
                })
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Employee history retrieved successfully",
                "data": result
            }, status=status.HTTP_200_OK)
            
        except BaseUserModel.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Employee not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving employee history: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminSitesListAPIView(APIView):
    """
    Get all sites created by admin - Optimized
    GET: /api/admin/sites/ - List all sites for current admin (if admin role)
    GET: /api/admin/sites/?admin_id=<admin_id> - List all sites for specific admin (if organization role)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id=None):
        """Get all sites for admin, optionally filtered by site_id - Optimized"""
        try:
            admin_user = None
            
            # Get admin_id based on role
            if request.user.role == 'admin':
                # Admin role: always use request.user
                admin_user = request.user
                admin_id = request.user.id
            elif request.user.role == 'organization':
                # Organization role: get admin_id from query params (optional)
                admin_id = request.query_params.get('admin_id')
                
                if admin_id:
                    # If admin_id provided, validate and get sites for that admin
                    try:
                        # Don't use select_related with only() as it causes conflicts
                        admin_user = BaseUserModel.objects.only(
                            'id', 'role', 'email'
                        ).get(id=admin_id, role='admin')
                        
                        # O(1) query - Verify admin belongs to organization
                        admin_profile = AdminProfile.objects.select_related('user', 'organization').only(
                            'id', 'user_id', 'organization_id'
                        ).filter(
                            user=admin_user,
                            organization=request.user
                        ).first()
                        
                        if not admin_profile:
                            return Response({
                                "status": status.HTTP_403_FORBIDDEN,
                                "message": "Admin does not belong to your organization",
                                "data": []
                            }, status=status.HTTP_403_FORBIDDEN)
                    except BaseUserModel.DoesNotExist:
                        return Response({
                            "status": status.HTTP_404_NOT_FOUND,
                            "message": "Admin not found",
                            "data": []
                        }, status=status.HTTP_404_NOT_FOUND)
                else:
                    # If no admin_id provided, get all admins under organization and return all their sites
                    admin_profiles = AdminProfile.objects.filter(
                        organization=request.user
                    ).select_related('user').only('id', 'user_id', 'organization_id')
                    
                    admin_user_ids = [ap.user_id for ap in admin_profiles]
                    
                    if not admin_user_ids:
                        return Response({
                            "status": status.HTTP_200_OK,
                            "message": "No admins found under your organization",
                            "data": []
                        }, status=status.HTTP_200_OK)
                    
                    # Get all sites for all admins under this organization - O(1) query
                    # Include created_by_admin__own_admin_profile for serializer access
                    sites = Site.objects.filter(
                        created_by_admin_id__in=admin_user_ids,
                        is_active=True
                    ).select_related(
                        'organization', 
                        'created_by_admin',
                        'created_by_admin__own_admin_profile'
                    ).only(
                        'id', 'organization_id', 'created_by_admin_id', 'site_name', 
                        'address', 'city', 'state', 'pincode', 'contact_person', 
                        'contact_number', 'description', 'is_active', 'created_at', 'updated_at'
                    ).order_by('site_name')
                    
                    serializer = SiteSerializer(sites, many=True)
                    return Response({
                        "status": status.HTTP_200_OK,
                        "message": "Sites retrieved successfully",
                        "data": serializer.data
                    }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
                    "data": []
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Build queryset - O(1) query using index site_admin_active_idx
            sites = Site.objects.filter(
                created_by_admin=admin_user,
                is_active=True
            )
            
            # Filter by site_id if provided (for filtering/validation purposes)
            if site_id:
                sites = sites.filter(id=site_id)
            
            # Include created_by_admin__own_admin_profile in select_related for serializer access
            sites = sites.select_related(
                'organization', 
                'created_by_admin', 
                'created_by_admin__own_admin_profile'
            ).only(
                'id', 'organization_id', 'created_by_admin_id', 'site_name', 
                'address', 'city', 'state', 'pincode', 'contact_person', 
                'contact_number', 'description', 'is_active', 'created_at', 'updated_at'
            ).order_by('site_name')
            
            # Use serializer for proper UUID handling
            serializer = SiteSerializer(sites, many=True)
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Sites retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving sites: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SiteEmployeesAPIView(APIView):
    """
    Get all employees assigned to a specific site - Optimized
    GET: /api/sites/{site_id}/employees/ - Get employees for site
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        """Get employees assigned to site - Optimized"""
        try:
            # O(1) query - Validate site
            site = Site.objects.only('id', 'created_by_admin_id', 'is_active', 'site_name', 
                                     'address', 'city', 'state').get(id=site_id, is_active=True)
            
            # Verify admin has access to this site
            if request.user.role == 'admin' and site.created_by_admin_id != request.user.id:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have access to this site",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get active assignments for this site - O(1) query using index assignment_site_dates_idx
            assignments = EmployeeAdminSiteAssignment.objects.filter(
                site=site,
                is_active=True
            ).select_related(
                'employee', 'employee__own_user_profile', 
                'admin', 'admin__own_admin_profile'
            ).only(
                'id', 'employee_id', 'admin_id', 'start_date', 'end_date', 
                'is_active'
            )
            
            employees_data = []
            for assignment in assignments:
                employee_profile = assignment.employee.own_user_profile
                admin_profile = assignment.admin.own_admin_profile if hasattr(assignment.admin, 'own_admin_profile') else None
                
                employees_data.append({
                    'employee_id': str(assignment.employee.id),
                    'employee_name': employee_profile.user_name if employee_profile else assignment.employee.email,
                    'employee_email': assignment.employee.email,
                    'custom_employee_id': employee_profile.custom_employee_id if employee_profile else None,
                    'admin_id': str(assignment.admin.id),
                    'admin_name': admin_profile.admin_name if admin_profile else assignment.admin.email,
                    'assignment_start_date': assignment.start_date,
                    'assignment_end_date': assignment.end_date,
                    'is_active': assignment.is_active,
                    'designation': employee_profile.designation if employee_profile else None,
                    'job_title': employee_profile.job_title if employee_profile else None,
                })
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Site employees retrieved successfully",
                "data": {
                    'site_id': site.id,
                    'site_name': site.site_name,
                    'site_address': site.address,
                    'site_city': site.city,
                    'site_state': site.state,
                    'employees': employees_data,
                    'total_employees': len(employees_data)
                }
            }, status=status.HTTP_200_OK)
            
        except Site.DoesNotExist:
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Site not found",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving site employees: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminSiteEmployeesAPIView(APIView):
    """
    Get employees for admin's selected site - Optimized
    GET: /api/admin/site-employees/ - Get employees for admin's current site (from query param)
    GET: /api/admin/site-employees/?site_id={site_id} - Get employees for specific site
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get employees for admin's site - Optimized"""
        try:
            if request.user.role != 'admin':
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Only admins can access this endpoint",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            site_id = request.query_params.get('site_id')
            
            if not site_id:
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "site_id query parameter is required",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # O(1) query - Verify site belongs to admin using index site_id_admin_idx
            site = Site.objects.filter(
                id=site_id, 
                created_by_admin=request.user, 
                is_active=True
            ).only('id', 'site_name', 'address', 'city', 'state').first()
            
            if not site:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Site not found or you don't have access to this site",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get active assignments for this site under this admin using common function
            employee_ids = get_employees_assigned_to_site(
                request.user.id, site_id, check_date=None, active_only=True
            )
            
            # Get assignments with employee profiles - O(1) query
            assignments = EmployeeAdminSiteAssignment.objects.filter(
                site=site,
                admin=request.user,
                employee_id__in=employee_ids,
                is_active=True
            ).select_related(
                'employee', 'employee__own_user_profile'
            ).only(
                'id', 'employee_id', 'start_date', 'end_date'
            ).order_by('employee__own_user_profile__user_name')
            
            employees_data = []
            for assignment in assignments:
                employee_profile = assignment.employee.own_user_profile
                if not employee_profile:
                    continue
                
                employees_data.append({
                    'employee_id': str(assignment.employee.id),
                    'employee_name': employee_profile.user_name,
                    'employee_email': assignment.employee.email,
                    'custom_employee_id': employee_profile.custom_employee_id,
                    'designation': employee_profile.designation,
                    'job_title': employee_profile.job_title,
                    'phone_number': assignment.employee.phone_number,
                    'assignment_start_date': assignment.start_date,
                    'assignment_end_date': assignment.end_date,
                    'is_active': assignment.employee.is_active,
                    'profile_photo': employee_profile.profile_photo.url if employee_profile.profile_photo else None,
                })
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Site employees retrieved successfully",
                "data": {
                    'site': {
                        'id': site.id,
                        'name': site.site_name,
                        'address': site.address,
                        'city': site.city,
                        'state': site.state
                    },
                    'employees': employees_data,
                    'total_employees': len(employees_data)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving site employees: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
