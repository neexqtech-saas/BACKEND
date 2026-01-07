"""
Contact Management Serializers
"""
from rest_framework import serializers
from .models import Contact
from AuthN.models import BaseUserModel


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model"""
    admin_email = serializers.EmailField(source='admin.email', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    business_card_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'admin', 'admin_email', 'user', 'user_email',
            'full_name', 'company_name', 'job_title', 'department',
            'mobile_number', 'alternate_phone', 'office_landline', 'fax_number',
            'email_address', 'alternate_email',
            'full_address', 'state', 'city', 'country', 'pincode',
            'whatsapp_number',
            'additional_notes',
            'business_card_image', 'business_card_image_url',
            'source_type', 'created_by', 'created_by_email', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'admin', 'user']
    
    def get_business_card_image_url(self, obj):
        """Get full URL for business card image"""
        if obj.business_card_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.business_card_image.url)
            return obj.business_card_image.url
        return None


class ContactCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating contacts"""
    
    class Meta:
        model = Contact
        fields = [
            'full_name', 'company_name', 'job_title', 'department',
            'mobile_number', 'alternate_phone', 'office_landline', 'fax_number',
            'email_address', 'alternate_email',
            'full_address', 'state', 'city', 'country', 'pincode',
            'whatsapp_number',
            'additional_notes',
            'business_card_image', 'source_type'
        ]
        extra_kwargs = {
            'full_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'company_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'job_title': {'required': False, 'allow_blank': True, 'allow_null': True},
            'department': {'required': False, 'allow_blank': True, 'allow_null': True},
            'mobile_number': {'required': False, 'allow_blank': True, 'allow_null': True},  # Made optional, will use default if empty
            'alternate_phone': {'required': False, 'allow_blank': True, 'allow_null': True},
            'office_landline': {'required': False, 'allow_blank': True, 'allow_null': True},
            'fax_number': {'required': False, 'allow_blank': True, 'allow_null': True},
            'email_address': {'required': False, 'allow_blank': True, 'allow_null': True},
            'alternate_email': {'required': False, 'allow_blank': True, 'allow_null': True},
            'full_address': {'required': False, 'allow_blank': True, 'allow_null': True},
            'state': {'required': False, 'allow_blank': True, 'allow_null': True},
            'city': {'required': False, 'allow_blank': True, 'allow_null': True},
            'country': {'required': False, 'allow_blank': True, 'allow_null': True},
            'pincode': {'required': False, 'allow_blank': True, 'allow_null': True},
            'whatsapp_number': {'required': False, 'allow_blank': True, 'allow_null': True},
            'additional_notes': {'required': False, 'allow_blank': True, 'allow_null': True},
            'business_card_image': {'required': False, 'allow_null': True},
            'source_type': {'required': False},
        }
    
    def validate(self, attrs):
        """Clean empty strings and set defaults"""
        # Convert empty strings to None for all fields
        for field_name in attrs:
            if attrs[field_name] == '':
                attrs[field_name] = None
        
        # Set default for mobile_number if not provided or empty
        if not attrs.get('mobile_number'):
            attrs['mobile_number'] = ''
        
        # Set default for source_type if not provided
        if not attrs.get('source_type'):
            attrs['source_type'] = 'manual'
        
        return attrs


class ContactExtractionResultSerializer(serializers.Serializer):
    """Serializer for OCR extraction results"""
    full_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    company_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    job_title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    mobile_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    alternate_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    office_landline = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fax_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email_address = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    alternate_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    full_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    state = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pincode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    whatsapp_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    additional_notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

