from django.urls import path
from .views import *

urlpatterns = [
    path('staff-list/<uuid:site_id>/', StaffListByAdmin.as_view(), name="staff-list-by-admin-site"),
]