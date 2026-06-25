from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from b2b_admin.models import Driver
from operations.models import Shipment
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import math

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lng points."""
    R = 6371000 # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2.0)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

@method_decorator(csrf_exempt, name='dispatch')
class UpdateShipmentStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    # BUG-002: Strict state machine — define valid transitions
    VALID_TRANSITIONS = {
        'ACTIVE': ['IN_TRANSIT'],
        'IN_TRANSIT': ['PENDING_APPROVAL'],
    }
    
    # BUG-005: Geofence tolerance in meters (increased from 50m to 200m for GPS jitter)
    GEOFENCE_TOLERANCE_METERS = 200
    
    def post(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
        except Driver.DoesNotExist:
            return Response({'error': 'Unauthorized. Not a driver.'}, status=status.HTTP_403_FORBIDDEN)
            
        shipment_id = request.data.get('shipment_id')
        new_status = request.data.get('status')
        
        if new_status not in ['IN_TRANSIT', 'PENDING_APPROVAL']:
            return Response({'error': 'Invalid status update.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            shipment = Shipment.objects.get(id=shipment_id, driver=driver)
            
            # BUG-002: Enforce strict state machine transitions
            allowed = self.VALID_TRANSITIONS.get(shipment.status, [])
            if new_status not in allowed:
                return Response(
                    {'error': f'Cannot transition from {shipment.status} to {new_status}. Allowed transitions: {", ".join(allowed) if allowed else "none"}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if new_status == 'PENDING_APPROVAL':
                # 1. Geofence Verification
                lat = request.data.get('lat')
                lng = request.data.get('lng')
                proof_url = request.data.get('proof_of_delivery_url')
                
                if lat is None or lng is None:
                    return Response({'error': 'GPS coordinates are required to verify delivery.'}, status=status.HTTP_400_BAD_REQUEST)
                if not proof_url:
                    return Response({'error': 'Proof of delivery image URL is required.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                dest_lat = shipment.order.destination_lat
                dest_lng = shipment.order.destination_lng
                
                # BUG-001: Handle None destination coordinates gracefully
                if dest_lat is not None and dest_lng is not None:
                    distance = haversine(float(lat), float(lng), dest_lat, dest_lng)
                    
                    # BUG-005: Use 200m tolerance instead of 50m
                    if distance > self.GEOFENCE_TOLERANCE_METERS:
                        return Response(
                            {'error': f'You must be within {self.GEOFENCE_TOLERANCE_METERS} meters of the destination. Current distance: {int(distance)}m.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                # If dest coords are None, skip geofence check (client had no GPS pin)
                
                # 2. Update Shipment
                shipment.status = 'PENDING_APPROVAL'
                shipment.proof_of_delivery_url = proof_url
                
                from operations.models import Notification
                Notification.objects.create(
                    company=shipment.order.company,
                    message=f"Driver {driver.name} submitted Proof of Delivery for Order #{shipment.order.order_number}. Awaiting your approval."
                )
                
            elif new_status == 'IN_TRANSIT':
                vehicle_info = request.data.get('vehicle_info')
                if not vehicle_info:
                    return Response({'error': 'Vehicle information is required to start the trip.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                shipment.vehicle_info = vehicle_info
                shipment.status = 'IN_TRANSIT'
                
                order = shipment.order
                order.status = 'IN_TRANSIT'
                order.save(update_fields=['status'])
                
            shipment.save()
            
            return Response({'message': f'Shipment status updated to {new_status}.'}, status=status.HTTP_200_OK)
            
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found or not assigned to you.'}, status=status.HTTP_404_NOT_FOUND)
