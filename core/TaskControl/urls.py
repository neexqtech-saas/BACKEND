"""
Task Management URLs
"""

from django.urls import path
from .views import TaskTypeAPIView
from .advanced_views import (
    TaskAPIView, TaskCommentAPIView
)
from .additional_utility_views import *
from .employee_views import (
    EmployeeTaskListView, EmployeeUpdateTaskStatusView
)

urlpatterns = [
    # Task Types
    path('task-types/<uuid:site_id>/', TaskTypeAPIView.as_view(), name='task-type-list-create'),
    path('task-types/<uuid:site_id>/<int:pk>/', TaskTypeAPIView.as_view(), name='task-type-detail'),
    
    # Tasks
    path('task-list-create/<uuid:site_id>/', TaskAPIView.as_view(), name='task-list-create'),
    path('task-list-create-by-user/<uuid:site_id>/<uuid:user_id>/', TaskAPIView.as_view(), name='task-list-create-by-user'),
    path('task-detail-update-delete/<uuid:site_id>/<uuid:user_id>/<int:pk>/', TaskAPIView.as_view(), name='task-detail-update-delete'),
    
    # Task Comments
    path('task-comments/<int:task_id>/', TaskCommentAPIView.as_view(), name='task-comments'),
    
    # Additional Utility APIs
    path('dashboard/<uuid:site_id>/', TaskDashboardAPIView.as_view(), name='task-dashboard'),
    path('employee-tasks/<uuid:site_id>/<uuid:user_id>/', EmployeeTaskListAPIView.as_view(), name='employee-tasks'),
    
    # Employee Task Management APIs
    path('employee/my-tasks/<uuid:site_id>/<uuid:user_id>/', EmployeeTaskListView.as_view(), name='employee-my-tasks'),
    path('employee/update-task-status/<uuid:site_id>/<int:task_id>/', EmployeeUpdateTaskStatusView.as_view(), name='employee-update-task-status'),
]
