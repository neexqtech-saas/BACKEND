"""
Invoice Management Serializers
"""

from rest_framework import serializers
from .models import Invoice
from AuthN.models import BaseUserModel
import json


class FlexibleJSONField(serializers.JSONField):
    """JSONField that accepts both JSON strings and parsed JSON objects"""
    
    def to_internal_value(self, data):
        if data is None:
            return None
        
        # If it's already a list or dict, return as is (don't validate again)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data
        
        # Handle DRF's JSONString wrapper (when data is already parsed but wrapped)
        # Check if it's a JSONString-like object that has the actual data
        if hasattr(data, '__iter__') and not isinstance(data, (str, bytes)):
            # Try to convert to list/dict if it's iterable
            try:
                if isinstance(data, (list, dict)):
                    return data
                # If it's a JSONString wrapper, try to get the underlying value
                data_str = str(data)
                # If the string representation looks like a Python list/dict, use eval (safe for our use case)
                if (data_str.startswith('[') and data_str.endswith(']')) or (data_str.startswith('{') and data_str.endswith('}')):
                    try:
                        # Use ast.literal_eval for safe evaluation of Python literals
                        import ast
                        parsed = ast.literal_eval(data_str)
                        return parsed
                    except (ValueError, SyntaxError):
                        # Fall through to string parsing
                        pass
            except Exception:
                pass
        
        # Handle string input (from FormData)
        if isinstance(data, str):
            # Strip whitespace
            data = data.strip()
            if not data:
                return []
            try:
                parsed = json.loads(data)
                # Validate it's a list or dict
                if not isinstance(parsed, (list, dict)):
                    return []
                return parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                # Try ast.literal_eval if json.loads fails (for Python-style strings)
                try:
                    import ast
                    parsed = ast.literal_eval(data)
                    if isinstance(parsed, (list, dict)):
                        return parsed
                except (ValueError, SyntaxError):
                    pass
                # Return empty list instead of failing
                return []
        
        # For any other type, try to convert to string and parse
        try:
            data_str = str(data)
            # Try json.loads first
            try:
                parsed = json.loads(data_str)
                if isinstance(parsed, (list, dict)):
                    return parsed
            except:
                # Try ast.literal_eval for Python-style literals
                import ast
                parsed = ast.literal_eval(data_str)
                if isinstance(parsed, (list, dict)):
                    return parsed
        except Exception:
            pass
        
        return []


class InvoiceItemSerializer(serializers.Serializer):
    """Invoice Item Serializer for JSON field"""
    id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField()
    hsn_sac = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    rate = serializers.DecimalField(max_digits=15, decimal_places=2)
    sgst_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    cgst_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    cess_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class InvoiceSerializer(serializers.ModelSerializer):
    """Invoice Serializer with items as JSON"""
    items = serializers.JSONField(required=False, allow_null=True)
    admin_email = serializers.EmailField(source='admin.email', read_only=True)
    business_logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at']
    
    def get_business_logo_url(self, obj):
        if obj.business_logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.business_logo.url)
            return obj.business_logo.url
        return None
    
    def to_representation(self, instance):
        """Format items for response"""
        data = super().to_representation(instance)
        
        # Get items from instance directly (from database)
        items = instance.items if hasattr(instance, 'items') else data.get('items')
        
        # Ensure items is always a list
        if items is None:
            items = []
        elif not isinstance(items, list):
            items = []
        
        # Format items with display fields
        formatted_items = []
        for item in items:
            if isinstance(item, dict):
                formatted_item = dict(item)
            else:
                # If item is not a dict, skip it
                continue
                
            # Add display fields for percentages
            sgst = formatted_item.get('sgst_percent', 0)
            cgst = formatted_item.get('cgst_percent', 0)
            cess = formatted_item.get('cess_percent', 0)
            
            # Convert to float if string
            if isinstance(sgst, str):
                sgst = float(sgst) if sgst else 0
            if isinstance(cgst, str):
                cgst = float(cgst) if cgst else 0
            if isinstance(cess, str):
                cess = float(cess) if cess else 0
                
            formatted_item['sgst_percent_display'] = f"{sgst}%"
            formatted_item['cgst_percent_display'] = f"{cgst}%"
            formatted_item['cess_percent_display'] = f"{cess}%"
            formatted_items.append(formatted_item)
        
        data['items'] = formatted_items
        return data


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """Invoice Create Serializer with items as JSON"""
    items = FlexibleJSONField(required=False, allow_null=True)
    
    class Meta:
        model = Invoice
        fields = [
            'invoice_date', 'due_date', 'status', 'theme_color',
            'business_name', 'business_contact_name', 'business_gstin',
            'business_address_line1', 'business_city', 'business_state',
            'business_country', 'business_pincode', 'business_logo',
            'client_name', 'client_gstin', 'client_address_line1',
            'client_city', 'client_state', 'client_country', 'client_pincode',
            'place_of_supply', 'sub_total', 'total_sgst', 'total_cgst', 'total_cess', 'total_amount',
            'notes', 'terms_and_conditions', 'items'
        ]
        read_only_fields = ['id', 'invoice_number']
    
    def validate_items(self, value):
        """Validate items"""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return value
    
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        admin = self.context.get('admin')
        
        if not admin:
            raise serializers.ValidationError("Admin is required to create an invoice")
        
        # Process items - convert to proper format
        if items_data and len(items_data) > 0:
            processed_items = []
            for idx, item in enumerate(items_data):
                processed_item = {
                    'id': item.get('id', idx + 1),
                    'description': item.get('description', ''),
                    'hsn_sac': item.get('hsn_sac', ''),
                    'quantity': float(item.get('quantity', 1)),
                    'rate': float(item.get('rate', 0)),
                    'sgst_percent': float(item.get('sgst_percent', 0)),
                    'cgst_percent': float(item.get('cgst_percent', 0)),
                    'cess_percent': float(item.get('cess_percent', 0)),
                    'amount': float(item.get('amount', 0))
                }
                processed_items.append(processed_item)
            validated_data['items'] = processed_items
        else:
            validated_data['items'] = []
        
        invoice = Invoice.objects.create(admin=admin, **validated_data)
        return invoice


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    """Invoice Update Serializer with items as JSON"""
    items = FlexibleJSONField(required=False, allow_null=True)
    
    class Meta:
        model = Invoice
        fields = [
            'invoice_date', 'due_date', 'status', 'theme_color',
            'business_name', 'business_contact_name', 'business_gstin',
            'business_address_line1', 'business_city', 'business_state',
            'business_country', 'business_pincode', 'business_logo',
            'client_name', 'client_gstin', 'client_address_line1',
            'client_city', 'client_state', 'client_country', 'client_pincode',
            'place_of_supply', 'sub_total', 'total_sgst', 'total_cgst', 'total_cess', 'total_amount',
            'notes', 'terms_and_conditions', 'items'
        ]
        read_only_fields = ['id', 'invoice_number', 'admin']
    
    def validate_items(self, value):
        """Validate items"""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return value
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update invoice fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update items if provided
        if items_data is not None:
            # Process items - convert to proper format
            if items_data:
                processed_items = []
                for idx, item in enumerate(items_data):
                    processed_item = {
                        'id': item.get('id', idx + 1),
                        'description': item.get('description', ''),
                        'hsn_sac': item.get('hsn_sac', ''),
                        'quantity': float(item.get('quantity', 1)),
                        'rate': float(item.get('rate', 0)),
                        'sgst_percent': float(item.get('sgst_percent', 0)),
                        'cgst_percent': float(item.get('cgst_percent', 0)),
                        'cess_percent': float(item.get('cess_percent', 0)),
                        'amount': float(item.get('amount', 0))
                    }
                    processed_items.append(processed_item)
                instance.items = processed_items
            else:
                instance.items = []
        
        instance.save()
        return instance


class InvoiceListSerializer(serializers.ModelSerializer):
    """Invoice List Serializer (lightweight)"""
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date', 'status',
            'client_name', 'total_amount', 'items_count',
            'created_at', 'updated_at'
        ]
    
    def get_items_count(self, obj):
        if isinstance(obj.items, list):
            return len(obj.items)
        return 0

