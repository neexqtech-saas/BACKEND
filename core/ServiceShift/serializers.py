# serializers.py
from rest_framework import serializers
from .models import ServiceShift



class ServiceShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceShift
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ServiceShiftUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceShift
        fields = '__all__'
        read_only_fields = ['id', 'admin', 'created_at', 'updated_at']