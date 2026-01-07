"""
Asset Management Admin
"""

from django.contrib import admin
from .models import AssetCategory, Asset


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'admin', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['asset_code', 'name', 'category', 'status', 'condition', 'admin', 'is_active']
    list_filter = ['status', 'condition', 'is_active', 'category']
    search_fields = ['asset_code', 'name', 'serial_number']
    readonly_fields = ['id', 'created_at', 'updated_at']

