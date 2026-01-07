# urls.py

from django.urls import path
from .views import LocationAPIView, AssignLocationToUserAPIView

urlpatterns = [
    # Location CRUD
    path('locations/<uuid:site_id>/', LocationAPIView.as_view(), name='location-list-create'),
    path('locations/<uuid:site_id>/<int:pk>/', LocationAPIView.as_view(), name='location-detail'),
    
    # Assign Locations to User
    path('assign-locations/<uuid:site_id>/<uuid:user_id>/', AssignLocationToUserAPIView.as_view(), name='assign-locations-to-user'),
    path('assign-locations/<uuid:site_id>/<uuid:user_id>/<int:location_id>/', AssignLocationToUserAPIView.as_view(), name='remove-location-from-user'),
]