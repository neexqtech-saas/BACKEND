"""
Contact Management URLs
"""
from django.urls import path
from .views import (
    ContactAPIView, ContactExtractAPIView, ContactStatsAPIView
)

urlpatterns = [
    # Contact CRUD Operations
    path('contact-list-create/<uuid:site_id>/', ContactAPIView.as_view(), name='contact-list-create'),
    path('contact-list-create-by-user/<uuid:site_id>/<uuid:user_id>/', ContactAPIView.as_view(), name='contact-list-create-by-user'),
    path('contact-detail-update-delete/<uuid:site_id>/<uuid:user_id>/<int:pk>/', ContactAPIView.as_view(), name='contact-detail-update-delete'),
    
    # OCR Extraction
    path('contact-extract/<uuid:site_id>/', ContactExtractAPIView.as_view(), name='contact-extract'),
    path('contact-extract-by-user/<uuid:site_id>/<uuid:user_id>/', ContactExtractAPIView.as_view(), name='contact-extract-by-user'),
    
    # Statistics
    path('contact-stats/<uuid:site_id>/', ContactStatsAPIView.as_view(), name='contact-stats'),
    path('contact-stats-by-user/<uuid:site_id>/<uuid:user_id>/', ContactStatsAPIView.as_view(), name='contact-stats-by-user'),
]

