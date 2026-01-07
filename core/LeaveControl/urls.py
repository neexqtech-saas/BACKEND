"""
Simple Leave Management URLs
Flexible: Supports both admin_id (view all) and user_id (view specific)
"""

from django.urls import path
from .views import (
    LeaveTypeAPIView, 
    EmployeeLeaveBalanceAPIView, 
    AssignLeaveAPIView,
    LeaveApplicationAPIView
)

urlpatterns = [
    # ==================== LEAVE TYPES ====================
    path('leave-types/<uuid:site_id>/', LeaveTypeAPIView.as_view(), name='leave-type-list-create'),
    path('leave-types/<uuid:site_id>/<int:pk>/', LeaveTypeAPIView.as_view(), name='leave-type-detail'),
    
    # ==================== ASSIGN LEAVES (Single & Bulk) ====================
    path('assign-leaves/<uuid:site_id>/', AssignLeaveAPIView.as_view(), name='assign-leaves-admin'),
    path('assign-leaves/<uuid:site_id>/<uuid:user_id>/', AssignLeaveAPIView.as_view(), name='assign-leaves-user'),
    
    # ==================== LEAVE BALANCES (View Only) ====================
    # Admin routes (view all employees)
    path('leave-balances/<uuid:site_id>/', EmployeeLeaveBalanceAPIView.as_view(), name='admin-leave-balances-all'),
    path('leave-balances/<uuid:site_id>/<uuid:user_id>/', EmployeeLeaveBalanceAPIView.as_view(), name='admin-leave-balances-user'),
    path('leave-balances/<uuid:site_id>/<uuid:user_id>/<int:pk>/', EmployeeLeaveBalanceAPIView.as_view(), name='admin-leave-balance-detail'),
    
    
    # ==================== LEAVE APPLICATIONS ====================
    # Admin routes (view all employees)
    path('leave-applications/<uuid:site_id>/', LeaveApplicationAPIView.as_view(), name='admin-leave-apps-all'),
    path('leave-applications/<uuid:site_id>/<uuid:user_id>/', LeaveApplicationAPIView.as_view(), name='admin-leave-apps-user'),
    path('leave-applications/<uuid:site_id>/<uuid:user_id>/<int:pk>/', LeaveApplicationAPIView.as_view(), name='admin-leave-app-detail'),
]
