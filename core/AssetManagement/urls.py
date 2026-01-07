"""
Asset Management URLs
All URLs follow pattern: prefix/admin_id
"""

from django.urls import path
from .views import (
    AssetCategoryAPIView,
    AssetCategoryDetailAPIView,
    AssetAPIView,
    AssetDetailAPIView
)

urlpatterns = [
    # Asset Category URLs
    path('categories/<uuid:site_id>/', AssetCategoryAPIView.as_view(), name='asset-category-list-create'),
    path('categories/<uuid:site_id>/<uuid:pk>/', AssetCategoryDetailAPIView.as_view(), name='asset-category-detail'),
    
    # Asset URLs
    path('assets/<uuid:site_id>/', AssetAPIView.as_view(), name='asset-list-create'),
    path('assets/<uuid:site_id>/<int:pk>/', AssetDetailAPIView.as_view(), name='asset-detail'),
]
