from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Template views
    path('login/', views.driver_login_view, name='driver_login'),
    path('logout/', views.driver_logout_view, name='driver_logout'),
    path('set-password/', views.driver_set_password_view, name='driver_set_password'),
    path('dashboard/', views.driver_dashboard_view, name='driver_dashboard'),
    
    # API endpoints
    path('api/shipment/status/', api_views.UpdateShipmentStatusAPIView.as_view(), name='api_driver_update_status'),
]
