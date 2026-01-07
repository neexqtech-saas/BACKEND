"""
Employee Task Views
Views for employees to manage their assigned tasks
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import Task
from .serializers import TaskSerializer
from AuthN.models import BaseUserModel, AdminProfile
from SiteManagement.models import Site
from AuthN.permissions import IsUser


class EmployeeTaskListView(APIView):
    """
    Get all tasks assigned to the logged-in employee
    """
    permission_classes = [IsUser]
    
    def get(self, request, site_id, user_id):
        """Get all tasks assigned to the specified employee - Single optimized query"""
        try:
            # For employee role, admin_id is not required, but validate site exists
            try:
                site = Site.objects.get(id=site_id, is_active=True)
            except Site.DoesNotExist:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Site not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            from utils.site_filter_utils import filter_queryset_by_site
            
            user = BaseUserModel.objects.filter(id=user_id, role='user').only('id').first()
            if not user:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "User not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Optimized query with index (assigned_to, status, created_at)
            # Employee view: show all tasks assigned to them regardless of admin assignment
            queryset = Task.objects.filter(
                assigned_to_id=user_id
            ).select_related('task_type', 'assigned_to', 'assigned_by').order_by('-created_at')
            queryset = filter_queryset_by_site(queryset, site_id, 'site')
            
            # Apply status filter if provided - uses index
            status_filter = request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            # Apply priority filter if provided
            priority_filter = request.query_params.get('priority')
            if priority_filter:
                queryset = queryset.filter(priority=priority_filter)
            
            # Fetch only required fields
            queryset = queryset.only(
                'id', 'admin_id', 'task_type_id', 'title', 'description', 'priority', 'status',
                'assigned_to_id', 'assigned_by_id', 'start_date', 'due_date', 'start_time',
                'end_time', 'actual_hours', 'completed_at', 'progress_percentage',
                'created_at', 'updated_at'
            )
            
            # Apply range/limit parameter (default 50)
            limit_param = request.query_params.get('limit') or request.query_params.get('range')
            if limit_param:
                try:
                    limit = int(limit_param)
                    if limit > 0:
                        queryset = queryset[:limit]
                except ValueError:
                    pass  # Invalid limit, use default
            
            # If no limit specified, default to 50
            if not limit_param:
                queryset = queryset[:50]
            
            serializer = TaskSerializer(queryset, many=True)
            return Response({
                "status": status.HTTP_200_OK,
                "message": "Tasks fetched successfully",
                "data": serializer.data
            })
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeUpdateTaskStatusView(APIView):
    """
    Employee updates task status:
    - If status is 'pending' → changes to 'in_progress' (accept task)
    - If status is 'in_progress' → changes to 'completed' (complete task)
    """
    permission_classes = [IsUser]
    
    @transaction.atomic
    def put(self, request, site_id, task_id):
        """Update task status based on current status - Optimized"""
        try:
            # For employee role, validate site exists
            try:
                site = Site.objects.get(id=site_id, is_active=True)
            except Site.DoesNotExist:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Site not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            user = request.user
            # Single query with index optimization - admin_id is optional for employee tasks
            task = Task.objects.filter(
                id=task_id,
                assigned_to_id=user.id,
                site_id=site_id
            ).first()
            
            if not task:
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "Task not found or you don't have permission to update it",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Handle status transition based on current status
            if task.status == 'pending':
                # Accept task: pending → in_progress
                task.status = 'in_progress'
                task.start_time = timezone.now()  # Set start time when task is started
                task.save()
                
                serializer = TaskSerializer(task)
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Task accepted successfully. Status changed to 'in_progress'",
                    "data": serializer.data
                })
            
            elif task.status == 'in_progress':
                # Complete task: in_progress → completed
                # Comment is required when completing a task
                comment = request.data.get('comment', '').strip()
                if not comment:
                    return Response({
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "Comment is required when completing a task",
                        "data": None
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update task status
                task.status = 'completed'
                task.end_time = timezone.now()  # Set end time when task is completed
                task.completed_at = timezone.now()
                
                # Calculate actual hours if start_time exists
                if task.start_time and task.end_time:
                    time_delta = task.end_time - task.start_time
                    task.actual_hours = round(time_delta.total_seconds() / 3600, 2)  # Convert to hours
                
                # Add comment to task comments
                if not task.comments:
                    task.comments = []
                
                # Get user name for comment
                user_name = user.email
                if hasattr(user, 'own_user_profile') and user.own_user_profile:
                    user_name = user.own_user_profile.user_name
                
                # Add completion comment
                completion_comment = {
                    "comment": comment,
                    "user_id": str(user.id),
                    "user_name": user_name,
                    "user_email": user.email,
                    "created_at": timezone.now().isoformat(),
                    "type": "completion"
                }
                task.comments.append(completion_comment)
                
                task.save()
                
                serializer = TaskSerializer(task)
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "Task completed successfully. Status changed to 'completed'",
                    "data": serializer.data
                })
            
            else:
                # Task is already completed or in invalid state
                return Response({
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": f"Task status cannot be updated. Current status: {task.status}. Task can only be accepted when 'pending' or completed when 'in_progress'",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": str(e),
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

