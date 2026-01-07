from rest_framework import serializers
from .models import WeekOffPolicy


class WeekOffPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeekOffPolicy
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']



class WeekOffPolicyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeekOffPolicy
        fields = '__all__'
        read_only_fields = ['id', 'admin', 'created_at', 'updated_at']
