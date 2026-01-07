from django.urls import path
from .views import *

urlpatterns = [
    # Shift CRUD
    path('service-shifts/<uuid:site_id>/', ServiceShiftAPIView.as_view(), name='service-shift-list-create'),
    path('service-shifts/<uuid:site_id>/<int:pk>/', ServiceShiftAPIView.as_view(), name='service-shift-detail'),
    
    # Assign Shifts to User
    path('assign-shifts/<uuid:site_id>/<uuid:user_id>/', AssignShiftToUserAPIView.as_view(), name='assign-shifts-to-user'),
    path('assign-shifts/<uuid:site_id>/<uuid:user_id>/<int:shift_id>/', AssignShiftToUserAPIView.as_view(), name='remove-shift-from-user'),
]
