"""
Additional Utility APIs for Task Management
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, date

from .models import Task
from .serializers import TaskSerializer
from AuthN.models import BaseUserModel, AdminProfile
from SiteManagement.models import Site
from utils.pagination_utils import CustomPagination


class TaskDashboardAPIView(APIView):
    """Task Dashboard Statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, site_id):
        try:
            # Get admin_id based on role
            if request.user.role == 'admin':
                admin_id = request.user.id
                admin = request.user
            elif request.user.role == 'organization':
                # Organization role: get admin_id from query params
                admin_id = request.query_params.get('admin_id')
                if not admin_id:
                    return Response({
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "admin_id is required for organization role. Please provide admin_id as query parameter.",
                        "data": None
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate admin exists and belongs to organization
                try:
                    admin = BaseUserModel.objects.get(id=admin_id, role='admin')
                    # Verify admin belongs to organization
                    admin_profile = AdminProfile.objects.filter(
                        user=admin,
                        organization=request.user
                    ).first()
                    if not admin_profile:
                        return Response({
                            "status": status.HTTP_403_FORBIDDEN,
                            "message": "Admin does not belong to your organization",
                            "data": None
                        }, status=status.HTTP_403_FORBIDDEN)
                except BaseUserModel.DoesNotExist:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Admin not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate site belongs to admin
            try:
                site = Site.objects.get(id=site_id, created_by_admin=admin, is_active=True)
            except Site.DoesNotExist:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Site not found or you don't have permission to access this site",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            from utils.site_filter_utils import filter_queryset_by_site
            
            tasks = Task.objects.filter(admin=admin)
            tasks = filter_queryset_by_site(tasks, site_id, 'site')
            
            total_tasks = tasks.count()
            pending = tasks.filter(status='pending').count()
            in_progress = tasks.filter(status='in_progress').count()
            completed = tasks.filter(status='completed').count()
            overdue = tasks.filter(
                due_date__lt=date.today(),
                status__in=['pending', 'in_progress']
            ).count()
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Task dashboard data fetched successfully",
                "data": {
                    "total_tasks": total_tasks,
                    "pending": pending,
                    "in_progress": in_progress,
                    "completed": completed,
                    "overdue": overdue,
                    "completion_rate": round((completed / total_tasks * 100) if total_tasks > 0 else 0, 2)
                }
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeTaskListAPIView(APIView):
    """Get tasks assigned to an employee"""
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request, site_id, user_id):
        try:
            # Get admin_id based on role
            if request.user.role == 'admin':
                admin_id = request.user.id
                admin = request.user
            elif request.user.role == 'organization':
                # Organization role: get admin_id from query params
                admin_id = request.query_params.get('admin_id')
                if not admin_id:
                    return Response({
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "admin_id is required for organization role. Please provide admin_id as query parameter.",
                        "data": None
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate admin exists and belongs to organization
                try:
                    admin = BaseUserModel.objects.get(id=admin_id, role='admin')
                    # Verify admin belongs to organization
                    admin_profile = AdminProfile.objects.filter(
                        user=admin,
                        organization=request.user
                    ).first()
                    if not admin_profile:
                        return Response({
                            "status": status.HTTP_403_FORBIDDEN,
                            "message": "Admin does not belong to your organization",
                            "data": None
                        }, status=status.HTTP_403_FORBIDDEN)
                except BaseUserModel.DoesNotExist:
                    return Response({
                        "status": status.HTTP_404_NOT_FOUND,
                        "message": "Admin not found",
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Unauthorized access. Only admin and organization roles can access this endpoint",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate site belongs to admin
            try:
                site = Site.objects.get(id=site_id, created_by_admin=admin, is_active=True)
            except Site.DoesNotExist:
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "Site not found or you don't have permission to access this site",
                    "data": None
                }, status=status.HTTP_403_FORBIDDEN)
            
            from utils.site_filter_utils import filter_queryset_by_site
            user = get_object_or_404(BaseUserModel, id=user_id, role='user')
            
            tasks = Task.objects.filter(admin=admin, assigned_to=user)
            tasks = filter_queryset_by_site(tasks, site_id, 'site')
            
            status_filter = request.query_params.get('status')
            priority = request.query_params.get('priority')
            
            if status_filter:
                tasks = tasks.filter(status=status_filter)
            if priority:
                tasks = tasks.filter(priority=priority)
            
            tasks = tasks.order_by('-created_at')
            
            paginator = self.pagination_class()
            paginated_qs = paginator.paginate_queryset(tasks, request)
            
            serializer = TaskSerializer(paginated_qs, many=True)
            pagination_data = paginator.get_paginated_response(serializer.data)
            
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Tasks fetched successfully",
                "data": pagination_data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


