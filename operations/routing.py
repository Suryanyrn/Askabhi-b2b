from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/tracking/(?P<shipment_id>[^/]+)/$', consumers.LocationConsumer.as_asgi()),
]
