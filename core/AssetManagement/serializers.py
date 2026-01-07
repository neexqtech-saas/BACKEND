"""
Asset Management Serializers
"""

from rest_framework import serializers
from .models import AssetCategory, Asset
from AuthN.models import BaseUserModel


class AssetCategorySerializer(serializers.ModelSerializer):
    """Asset Category Serializer"""
    
    class Meta:
        model = AssetCategory
        fields = [
            'id', 'admin', 'name', 'code', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssetSerializer(serializers.ModelSerializer):
    """Asset Serializer"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Asset
        fields = [
            'id', 'admin', 'category', 'category_name',
            'asset_code', 'name', 'description', 'brand', 'model',
            'serial_number', 'status', 'condition', 'location',
            'purchase_date', 'purchase_price', 'current_value',
            'warranty_expiry', 'vendor', 'notes', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

