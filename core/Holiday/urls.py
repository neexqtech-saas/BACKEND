from django.urls import path
from .views import HolidayAPIView

urlpatterns = [
    path('holidays/<uuid:site_id>/', HolidayAPIView.as_view(), name='holiday-list-create'),
    path('holidays/<uuid:site_id>/<str:pk>/', HolidayAPIView.as_view(), name='holiday-detail'),
]
