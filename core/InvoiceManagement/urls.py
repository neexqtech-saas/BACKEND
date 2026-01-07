"""
Invoice Management URLs
"""

from django.urls import path
from .views import InvoiceAPIView

urlpatterns = [
    # Invoice CRUD
    path('invoices/<uuid:site_id>/', InvoiceAPIView.as_view(), name='invoice-list-create'),
    path('invoices/<uuid:site_id>/<int:pk>/', InvoiceAPIView.as_view(), name='invoice-detail'),
]

