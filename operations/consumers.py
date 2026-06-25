import json
import math
import time
from channels.generic.websocket import AsyncWebsocketConsumer

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lng points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.shipment_id = self.scope['url_route']['kwargs']['shipment_id']
        self.room_group_name = f'tracking_{self.shipment_id}'
        
        # For speed calculation
        self.last_lat = None
        self.last_lng = None
        self.last_time = None
        self.speed_kmh = 0.0
        
        # TWR-001: Rolling average speed buffer to smooth ETA fluctuations
        self.speed_history = []
        self.SPEED_HISTORY_SIZE = 5

        # Load destination coordinates
        self.dest_lat, self.dest_lng = await self.get_destination_coords()

        # Join tracking group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave tracking group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket (Driver App)
    async def receive(self, text_data):
        # Read-write Auth check: Only the assigned driver can send GPS data
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            return  # Drop unauthorized messages
            
        is_authorized = await self.is_driver_for_shipment(user, self.shipment_id)
        if not is_authorized:
            return  # Drop unauthorized messages
            
        text_data_json = json.loads(text_data)
        
        # Typically the driver app sends {"lat": 12.34, "lng": 56.78}
        lat = text_data_json.get('latitude') or text_data_json.get('lat')
        lng = text_data_json.get('longitude') or text_data_json.get('lng')
        
        if lat and lng:
            lat = float(lat)
            lng = float(lng)
            
            await self.update_shipment_location(lat, lng)
            
            # Calculate speed from last known position
            now = time.time()
            if self.last_lat is not None and self.last_time is not None:
                dt = now - self.last_time
                if dt > 0:
                    dist_moved = haversine(self.last_lat, self.last_lng, lat, lng)
                    instant_speed = (dist_moved / dt) * 3.6  # m/s to km/h
                    # Cap unrealistic speeds (GPS jitter)
                    if instant_speed > 200:
                        instant_speed = 0.0
                    
                    # TWR-001: Use rolling average instead of instantaneous speed
                    self.speed_history.append(instant_speed)
                    if len(self.speed_history) > self.SPEED_HISTORY_SIZE:
                        self.speed_history.pop(0)
                    self.speed_kmh = sum(self.speed_history) / len(self.speed_history)
            
            self.last_lat = lat
            self.last_lng = lng
            self.last_time = now
            
            # Calculate distance to destination
            distance_remaining = 0.0
            eta_minutes = None
            if self.dest_lat is not None and self.dest_lng is not None:
                distance_remaining = haversine(lat, lng, self.dest_lat, self.dest_lng)
                if self.speed_kmh > 1:  # Avoid division by zero / unrealistic when stationary
                    eta_minutes = round((distance_remaining / 1000) / self.speed_kmh * 60)

        # Send message to room group (Admin Dashboard listens here)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'location_update',
                'data': {
                    'lat': lat,
                    'lng': lng,
                    'distance_remaining_m': round(distance_remaining),
                    'speed_kmh': round(self.speed_kmh, 1),
                    'eta_minutes': eta_minutes,
                }
            }
        )

    # Receive message from room group
    async def location_update(self, event):
        data = event['data']

        # Send message to WebSocket (Admin Dashboard)
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'data': data
        }))

    from channels.db import database_sync_to_async
    @database_sync_to_async
    def update_shipment_location(self, lat, lng):
        from operations.models import Shipment
        try:
            shipment = Shipment.objects.get(id=self.shipment_id)
            shipment.current_lat = lat
            shipment.current_lng = lng
            shipment.save(update_fields=['current_lat', 'current_lng'])
        except Shipment.DoesNotExist:
            pass

    @database_sync_to_async
    def is_driver_for_shipment(self, user, shipment_id):
        from operations.models import Shipment
        try:
            shipment = Shipment.objects.get(id=shipment_id)
            if hasattr(user, 'driver') and shipment.driver.user == user:
                return True
        except Shipment.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def get_destination_coords(self):
        from operations.models import Shipment
        try:
            shipment = Shipment.objects.select_related('order').get(id=self.shipment_id)
            return shipment.order.destination_lat, shipment.order.destination_lng
        except Shipment.DoesNotExist:
            return None, None
