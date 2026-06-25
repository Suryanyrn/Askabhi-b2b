from django.urls import path
from . import api_views

urlpatterns = [
    path('api/client/create/', api_views.CreateClientAPIView.as_view(), name='api_create_client'),
    path('api/client/update/', api_views.UpdateClientAPIView.as_view(), name='api_update_client'),
    path('api/client/delete/', api_views.DeleteClientAPIView.as_view(), name='api_delete_client'),
    path('api/order/create/', api_views.CreateOrderAPIView.as_view(), name='api_create_order'),
    path('api/order/dispatch/', api_views.DispatchOrderAPIView.as_view(), name='api_dispatch_order'),
    path('api/order/delete/', api_views.DeleteOrderAPIView.as_view(), name='api_delete_order'),

    # Notifications
    path('api/notifications/', api_views.NotificationAPIView.as_view(), name='api_notifications'),
    
    # Manager Actions
    path('api/delivery/approve/', api_views.ApproveDeliveryAPIView.as_view(), name='api_approve_delivery'),
    
    # Mock Upload Endpoints
    path('api/upload/presigned-url/', api_views.MockPresignedUrlAPIView.as_view(), name='api_mock_presigned_url'),
    path('api/upload/direct/', api_views.MockDirectUploadAPIView.as_view(), name='api_mock_direct_upload'),
]
