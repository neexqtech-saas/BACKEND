"""
Site Management URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    # Site Management APIs
    path('sites/<str:admin_id>/', views.SiteAPIView.as_view(), name='site-list-create'),
    path('sites/<str:admin_id>/<uuid:site_id>/', views.SiteAPIView.as_view(), name='site-detail-update-delete'),
    
    # Employee Assignment APIs
    path('employee-assignments/<str:admin_id>/<str:employee_id>/', views.EmployeeAssignmentAPIView.as_view(), name='assignment-list-create'),
    path('employee-assignments/<str:admin_id>/<str:employee_id>/<uuid:assignment_id>/', views.EmployeeAssignmentAPIView.as_view(), name='assignment-detail-update-delete'),
    
    # Reporting APIs
    path('reports/employee-admins/<str:employee_id>/', views.EmployeeAdminsReportAPIView.as_view(), name='report-employee-admins'),
    path('reports/admin-employees/<str:admin_id>/', views.AdminEmployeesReportAPIView.as_view(), name='report-admin-employees'),
    path('reports/site-assignments/<uuid:site_id>/', views.SiteAssignmentsReportAPIView.as_view(), name='report-site-assignments'),
    path('reports/employee-history/<str:employee_id>/', views.EmployeeHistoryReportAPIView.as_view(), name='report-employee-history'),
    
    # Admin Site Selection APIs
    path('admin/sites/', views.AdminSitesListAPIView.as_view(), name='admin-sites-list'),
    path('admin/site-employees/', views.AdminSiteEmployeesAPIView.as_view(), name='admin-site-employees'),
    path('sites/<uuid:site_id>/employees/', views.SiteEmployeesAPIView.as_view(), name='site-employees'),
]

