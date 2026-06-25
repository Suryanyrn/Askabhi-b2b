from django.urls import path
from . import views
from . import api_views
from . import api_profile

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('health/',views.health,name='health'),
    path('managers/', views.managers_list, name='managers_list'),
    path('drivers/', views.drivers_list, name='drivers_list'),
    path('drivers/<uuid:driver_id>/', views.driver_profile_view, name='admin_driver_profile'),
    path('warehouse/', views.warehouse_list, name='warehouse_list'),
    path('products/', views.products_list, name='products_list'),
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/previous/', views.previous_orders_list, name='previous_orders_list'),
    path('shipments/', views.shipments_list, name='shipments_list'),
    path('clients/', views.clients_list, name='clients_list'),
    path('logout/', views.logout_user, name='logout_user'),
    path('api/personnel/create/', api_views.CreatePersonnelAPIView.as_view(), name='api_create_personnel'),
    path('api/personnel/update/', api_views.UpdatePersonnelAPIView.as_view(), name='api_update_personnel'),
    path('api/personnel/delete/', api_views.DeletePersonnelAPIView.as_view(), name='api_delete_personnel'),
    path('api/notifications/', api_views.NotificationAPIView.as_view(), name='api_notifications'),
    path('audit/', views.audit_logs_list, name='audit_logs_list'),
    path('inventory-logs/', views.inventory_logs_list, name='inventory_logs_list'),
    
    # Profile APIs
    path('api/profile/update/', api_profile.api_profile_update, name='api_profile_update'),
    path('api/profile/send-otp/', api_profile.api_profile_send_otp, name='api_profile_send_otp'),
    path('api/profile/verify-otp/', api_profile.api_profile_verify_otp, name='api_profile_verify_otp'),
    path('api/profile/change-password/', api_profile.api_profile_change_password, name='api_profile_change_password'),
]
