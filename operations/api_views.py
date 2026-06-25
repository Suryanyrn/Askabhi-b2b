import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, IntegrityError
from django.core.cache import cache
from b2b_admin.models import Client, Driver, Company, Manager
from logistics.models import Warehouse, Product, WarehouseStock
from operations.models import Order, OrderItem, Shipment
from b2b_manager.utils import log_action
import uuid
import datetime
from .models import Notification
logger = logging.getLogger('b2b_admin')
from b2b_admin.utils import get_user_company, get_display_name

class CreateClientAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        data = request.data
        try:
            client = Client.objects.create(
                company=company,
                name=data.get('name'),
                email=data.get('email'),
                phone=data.get('phone'),
                address=data.get('address'),
                latitude=float(data.get('latitude')) if data.get('latitude') else None,
                longitude=float(data.get('longitude')) if data.get('longitude') else None
            )
            
            log_action(request.user, f"Added Client: {client.name}")
            
            return Response({'message': 'Client created successfully', 'client_id': client.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Create Client Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while creating the client.'}, status=status.HTTP_400_BAD_REQUEST)

class CreateOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        data = request.data
        client_id = data.get('client_id')
        
        # Or create client on the fly
        client_name = data.get('client_name')
        client_email = data.get('client_email')
        client_phone = data.get('client_phone')
        client_address = data.get('client_address')
        client_lat = data.get('client_lat')
        client_lng = data.get('client_lng')
        
        items = data.get('items', []) # format: [{'product_id': '...', 'warehouse_id': '...', 'quantity': 10}]
        
        # BUG-004: Reject empty order creation
        if not items:
            return Response({'error': 'At least one item is required to create an order.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # GAP-002: Idempotency key to prevent duplicate orders from double-clicks
        idempotency_key = data.get('idempotency_key')
        if idempotency_key:
            cache_key = f"order_idemp_{company.company_id}_{idempotency_key}"
            existing_order_id = cache.get(cache_key)
            if existing_order_id:
                return Response({'message': 'Order already created', 'order_id': existing_order_id}, status=status.HTTP_200_OK)
        
        # PR-001: Sort items by product_id to ensure consistent lock ordering
        # and prevent database deadlocks when concurrent orders lock the same rows
        items = sorted(items, key=lambda x: str(x.get('product_id', '')))
        
        try:
            with transaction.atomic():
                if client_id:
                    client = Client.objects.get(id=client_id, company=company)
                else:
                    # MIS-001: Auto-create or get client by email/phone
                    # Catch IntegrityError from unique_together on (company, phone)
                    try:
                        client, created = Client.objects.get_or_create(
                            company=company,
                            email=client_email,
                            defaults={
                                'name': client_name,
                                'phone': client_phone,
                                'address': client_address,
                                'latitude': float(client_lat) if client_lat else None,
                                'longitude': float(client_lng) if client_lng else None
                            }
                        )
                    except IntegrityError:
                        raise Exception(
                            "A client with this phone number already exists under a different email. "
                            "Please use the correct email or update the existing client."
                        )
                
                # 1. Generate Order Number
                order_number = f"ORD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
                
                # 2. Create Order
                order = Order.objects.create(
                    order_number=order_number,
                    company=company,
                    client=client,
                    destination_address=client.address,
                    destination_lat=client.latitude,
                    destination_lng=client.longitude,
                    status='PLACED'
                )
                
                # 3. Create OrderItems & Deduct Stock immediately
                for item in items:
                    product_id = item.get('product_id')
                    warehouse_id = item.get('warehouse_id')
                    qty = int(item.get('quantity', 0))
                    
                    if qty <= 0: continue
                    
                    product = Product.objects.get(id=product_id, company=company)
                    warehouse = Warehouse.objects.get(id=warehouse_id, company=company)
                    
                    try:
                        # Lock the stock row
                        stock = WarehouseStock.objects.select_for_update().get(warehouse=warehouse, product=product)
                    except WarehouseStock.DoesNotExist:
                        raise Exception(f"Insufficient stock for {product.name} at {warehouse.name}. Available: 0, Requested: {qty}")
                        
                    if stock.stock_quantity < qty:
                        raise Exception(f"Insufficient stock for {product.name} at {warehouse.name}. Available: {stock.stock_quantity}, Requested: {qty}")
                        
                    # Deduct stock
                    stock.stock_quantity -= qty
                    stock.save()
                    
                    from logistics.models import InventoryLog
                    InventoryLog.objects.create(
                        company=company,
                        user_name=get_display_name(request.user),
                        product_name=product.name,
                        warehouse_name=warehouse.name,
                        action=f"Deducted {qty} units (Order #{order.order_number})"
                    )
                    
                    # Create OrderItem
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        warehouse=warehouse,
                        quantity=qty
                    )
                
                log_action(request.user, f"Created Order #{order.order_number} for {client.name}")
                
                # GAP-002: Cache idempotency key after successful creation
                if idempotency_key:
                    cache.set(cache_key, str(order.id), timeout=3600)  # 1 hour TTL
                    
                return Response({'message': 'Order created successfully', 'order_id': order.id}, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class DispatchOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        data = request.data
        order_id = data.get('order_id')
        driver_id = data.get('driver_id')
        route_geo_json = data.get('route_geo_json') # Passed from Leaflet Routing Machine frontend
        duration_seconds = data.get('duration')
        
        if not order_id or not driver_id:
            return Response({'error': 'Order ID and Driver ID are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order_id, company=company, status='PLACED')
                driver = Driver.objects.select_for_update().get(id=driver_id, company=company, is_available=True)
                
                # Update order status
                order.status = 'DISPATCHED'
                order.save()
                
                # Mark driver as unavailable
                driver.is_available = False
                driver.save()
                
                # Parse route if available
                parsed_route = None
                if route_geo_json:
                    import json
                    try:
                        parsed_route = json.loads(route_geo_json)
                    except:
                        pass
                
                # Calculate ETA if duration is provided
                eta = None
                if duration_seconds:
                    from django.utils import timezone
                    from datetime import timedelta
                    try:
                        duration_val = float(duration_seconds)
                        eta = timezone.now() + timedelta(seconds=duration_val)
                    except ValueError:
                        pass
                
                # Create shipment
                shipment = Shipment.objects.create(
                    order=order,
                    driver=driver,
                    status='ACTIVE',
                    route_geo_json=parsed_route,
                    estimated_duration=duration_seconds,
                    estimated_delivery_time=eta
                )
                
                # Log the Tracking URL for the client
                tracking_url = f"{request.scheme}://{request.get_host()}/track/{shipment.id}/"
                logger.info(f"Order #{order.order_number} Dispatched. Client Tracking URL: {tracking_url}")
                
                # Notify driver
                Notification.objects.create(
                    company=company,
                    message=f"Order #{order.order_number} has been dispatched to {driver.name}."
                )
                
                log_action(request.user, f"Dispatched Order #{order.order_number} with Driver {driver.name}")
            
            return Response({'message': 'Order dispatched successfully', 'shipment_id': shipment.id}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Dispatch Order Error: {str(e)}", exc_info=True)
            return Response({'error': 'Driver may be unavailable or Order is invalid.'}, status=status.HTTP_400_BAD_REQUEST)

class DeleteOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        order_id = request.data.get('order_id')
        
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order_id, company=company)
                
                if order.status != 'PLACED':
                    return Response({'error': 'Cannot delete an order that is already dispatched.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                # Restore stock
                for item in order.items.all():
                    stock = WarehouseStock.objects.select_for_update().get(warehouse=item.warehouse, product=item.product)
                    stock.stock_quantity += item.quantity
                    stock.save()
                    
                    from logistics.models import InventoryLog
                    InventoryLog.objects.create(
                        company=company,
                        user_name=get_display_name(request.user),
                        product_name=item.product.name,
                        warehouse_name=item.warehouse.name,
                        action=f"Restored {item.quantity} units (Order #{order.order_number} Deleted)"
                    )
                    
                order.delete()
                
                log_action(request.user, f"Deleted Order #{order.order_number}")
                
            return Response({'message': 'Order deleted and stock restored.'}, status=status.HTTP_200_OK)
            
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Delete Order Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while deleting the order.'}, status=status.HTTP_400_BAD_REQUEST)

class UpdateClientAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        client_id = request.data.get('client_id')
        try:
            client = Client.objects.get(id=client_id, company=company)
            
            client.name = request.data.get('name', client.name)
            client.email = request.data.get('email', client.email)
            client.phone = request.data.get('phone', client.phone)
            client.address = request.data.get('address', client.address)
            
            lat = request.data.get('latitude')
            lng = request.data.get('longitude')
            if lat is not None: client.latitude = float(lat)
            if lng is not None: client.longitude = float(lng)
            
            client.save()
            log_action(request.user, f"Updated Client: {client.name}")
            return Response({'message': 'Client updated successfully.'}, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Update Client Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while updating the client.'}, status=status.HTTP_400_BAD_REQUEST)

class DeleteClientAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        client_id = request.data.get('client_id')
        try:
            client = Client.objects.get(id=client_id, company=company)
            # Check for linked orders
            if Order.objects.filter(client=client).exists():
                return Response({'error': 'Cannot delete client with existing orders.'}, status=status.HTTP_400_BAD_REQUEST)
                
            client.delete()
            log_action(request.user, f"Deleted Client: {client.name}")
            return Response({'message': 'Client deleted successfully.'}, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Delete Client Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while deleting the client.'}, status=status.HTTP_400_BAD_REQUEST)
class ApproveDeliveryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        shipment_id = request.data.get('shipment_id')
        action = request.data.get('action') # 'approve' or 'reject'
        
        try:
            shipment = Shipment.objects.get(id=shipment_id, order__company=company, status='PENDING_APPROVAL')
            
            with transaction.atomic():
                if action == 'approve':
                    from django.utils import timezone
                    shipment.status = 'COMPLETED'
                    shipment.completed_at = timezone.now()
                    shipment.save()
                    
                    order = shipment.order
                    order.status = 'DELIVERED'
                    order.save(update_fields=['status'])
                    
                    driver = shipment.driver
                    driver.is_available = True
                    driver.save()
                    
                    log_action(request.user, f"Approved POD for Order #{order.order_number} (Driver: {driver.name})")
                    return Response({'message': 'Delivery approved successfully.'}, status=status.HTTP_200_OK)
                    
                elif action == 'reject':
                    shipment.status = 'IN_TRANSIT'
                    shipment.proof_of_delivery_url = None
                    shipment.save()
                    
                    # GAP-001: Create a notification for the driver about POD rejection
                    Notification.objects.create(
                        company=shipment.order.company,
                        message=f"POD REJECTED for Order #{shipment.order.order_number}. Please re-submit proof of delivery."
                    )
                    
                    # GAP-001: Send real-time WebSocket notification to driver
                    try:
                        from channels.layers import get_channel_layer
                        from asgiref.sync import async_to_sync
                        channel_layer = get_channel_layer()
                        if channel_layer:
                            async_to_sync(channel_layer.group_send)(
                                f'tracking_{shipment.id}',
                                {
                                    'type': 'location_update',
                                    'data': {
                                        'event': 'pod_rejected',
                                        'message': 'Your proof of delivery was rejected. Please re-submit.',
                                        'shipment_id': str(shipment.id),
                                    }
                                }
                            )
                    except Exception as ws_err:
                        logger.warning(f"Failed to send WebSocket POD rejection notification: {ws_err}")
                    
                    log_action(request.user, f"Rejected POD for Order #{shipment.order.order_number}")
                    return Response({'message': 'Delivery proof rejected. Driver notified to re-submit.'}, status=status.HTTP_200_OK)
                    
                else:
                    return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
                    
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found or not pending approval.'}, status=status.HTTP_404_NOT_FOUND)

class NotificationAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        notifications = Notification.objects.filter(company=company)
        
        unread_count = notifications.filter(is_read=False).count()
        data = [{
            'id': str(n.id),
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications[:20]]
        
        return Response({'unread_count': unread_count, 'notifications': data}, status=status.HTTP_200_OK)

    def post(self, request):
        company = get_user_company(request.user)
        if company:
            Notification.objects.filter(company=company, is_read=False).update(is_read=True)
            return Response({'message': 'Marked all as read.'}, status=status.HTTP_200_OK)
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

class MockPresignedUrlAPIView(APIView):
    permission_classes = [IsAuthenticated]
    """
    Mocks a service like Cloudinary or AWS S3 that generates a presigned URL
    for direct client upload, bypassing backend Pillow processing.
    """
    def get(self, request):
        from django.urls import reverse
        filename = request.GET.get('filename', 'upload.jpg')
        url = request.build_absolute_uri(reverse('api_mock_direct_upload'))
        return Response({'url': url, 'filename': filename}, status=status.HTTP_200_OK)

from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import os
import uuid
import mimetypes
from django.conf import settings

@method_decorator(csrf_exempt, name='dispatch')
class MockDirectUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    """
    Handles POD image uploads. Currently uses local FileSystemStorage.
    
    UXR-001: To switch to S3/Cloudinary at scale, set PROOF_UPLOAD_STORAGE_BACKEND
    and PROOF_UPLOAD_LOCATION in Django settings, or configure DEFAULT_FILE_STORAGE
    with django-storages. This avoids local disk exhaustion at 10,000+ users.
    
    TODO: Replace with django-storages S3Boto3Storage or Cloudinary backend
    before production deployment at scale.
    """
    # UXR-001: Max upload size configurable via settings (default 5MB)
    MAX_UPLOAD_SIZE = getattr(settings, 'PROOF_UPLOAD_MAX_SIZE', 5 * 1024 * 1024)
    
    def post(self, request):
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
        file = request.FILES['file']
        
        # Validate file size
        if file.size > self.MAX_UPLOAD_SIZE:
            max_mb = self.MAX_UPLOAD_SIZE // (1024 * 1024)
            return Response({'error': f'File size exceeds {max_mb}MB limit'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate file type
        file_type, _ = mimetypes.guess_type(file.name)
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if file_type not in allowed_types:
            return Response({'error': 'Only JPEG, PNG, and WebP images are allowed'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Sanitize filename
        ext = file.name.split('.')[-1] if '.' in file.name else 'jpg'
        safe_filename = f"{uuid.uuid4().hex}.{ext}"
        
        # UXR-001: Use configurable storage location from settings
        upload_location = getattr(settings, 'PROOF_UPLOAD_LOCATION', os.path.join(settings.BASE_DIR, 'media', 'proofs'))
        fs = FileSystemStorage(location=upload_location)
        filename = fs.save(safe_filename, file)
        file_url = f"/media/proofs/{filename}"
        
        return Response({'file_url': file_url}, status=status.HTTP_201_CREATED)
