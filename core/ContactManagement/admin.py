"""
Contact Management Admin
"""
from django.contrib import admin
from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'company_name', 'email_address', 'mobile_number',
        'source_type', 'created_by', 'created_at'
    ]
    list_filter = ['source_type', 'created_at', 'state', 'city']
    search_fields = [
        'full_name', 'company_name', 'email_address', 'mobile_number',
        'state', 'city', 'country'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

