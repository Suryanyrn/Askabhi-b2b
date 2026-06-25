from django.urls import path
from . import api_views

urlpatterns = [
    path('api/warehouse/create/', api_views.CreateWarehouseAPIView.as_view(), name='api_create_warehouse'),
    path('api/warehouse/update/', api_views.UpdateWarehouseAPIView.as_view(), name='api_update_warehouse'),
    path('api/warehouse/delete/', api_views.DeleteWarehouseAPIView.as_view(), name='api_delete_warehouse'),
    path('api/product/create/', api_views.CreateProductAPIView.as_view(), name='api_create_product'),
    path('api/product/update/', api_views.UpdateProductAPIView.as_view(), name='api_update_product'),
    path('api/product/delete/', api_views.DeleteProductAPIView.as_view(), name='api_delete_product'),
    path('api/stock/update/', api_views.UpdateStockAPIView.as_view(), name='api_update_stock'),
    path('api/stock/available/', api_views.GetStockAPIView.as_view(), name='api_get_stock'),
]
