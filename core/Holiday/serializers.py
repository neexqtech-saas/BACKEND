from rest_framework import serializers
from .models import Holiday


class HolidaySerializer(serializers.ModelSerializer):
    day = serializers.SerializerMethodField()

    class Meta:
        model = Holiday
        fields = '__all__'  # includes day automatically
        read_only_fields = ['id', 'created_at', 'updated_at', 'day']  # day is read-only

    def get_day(self, obj):
        # obj.holiday_date is assumed to be a DateField or DateTimeField
        return obj.holiday_date.strftime('%A') if obj.holiday_date else None


class HolidayUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'
        read_only_fields = ['id', 'admin', 'organization', 'created_at', 'updated_at']