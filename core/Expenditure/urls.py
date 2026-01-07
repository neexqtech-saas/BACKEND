"""
Expenditure URLs
"""

from django.urls import path
from .views import (
    ExpenseCategoryAPIView, ExpenseProjectAPIView,
    ExpenseAPIView, ExpenseApprovalAPIView
)

urlpatterns = [
    # Expense Category CRUD
    path('expense-categories/<uuid:site_id>/', ExpenseCategoryAPIView.as_view(), name='expense-category-list-create'),
    path('expense-categories/<uuid:site_id>/<int:pk>/', ExpenseCategoryAPIView.as_view(), name='expense-category-detail'),
    
    # Expense Project CRUD
    path('expense-projects/<uuid:site_id>/', ExpenseProjectAPIView.as_view(), name='expense-project-list-create'),
    path('expense-projects/<uuid:site_id>/<int:pk>/', ExpenseProjectAPIView.as_view(), name='expense-project-detail'),
    
    # Expense CRUD
    path('expenses/<uuid:site_id>/', ExpenseAPIView.as_view(), name='expense-list'),  # GET only - list all expenses
    path('expenses/<uuid:site_id>/<uuid:user_id>/', ExpenseAPIView.as_view(), name='expense-list-create-by-employee'),  # GET and POST
    
    # Expense Approval/Rejection
    path('expenses/<uuid:site_id>/<int:expense_id>/<str:action>/', ExpenseApprovalAPIView.as_view(), name='expense-approval'),
]
