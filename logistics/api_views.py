import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from onboarding.models import Company
from b2b_admin.models import Manager
from .models import Warehouse, Product, WarehouseStock
from .serializers import WarehouseSerializer, ProductSerializer, WarehouseStockSerializer
from b2b_manager.utils import log_action

logger = logging.getLogger('logistics')

from b2b_admin.utils import get_user_company, get_display_name

class CreateWarehouseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'You do not belong to a valid company.'}, status=status.HTTP_403_FORBIDDEN)
            
        name = request.data.get('name')
        location = request.data.get('location')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not name or not location:
            return Response({'error': 'Warehouse name and location are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                # Lock company row to prevent duplicates
                company = Company.objects.select_for_update().get(company_id=company.company_id)
                
                if Warehouse.objects.filter(company=company, name__iexact=name).exists():
                    return Response({'error': 'A warehouse with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                warehouse = Warehouse.objects.create(
                    company=company,
                    name=name,
                    location=location,
                    latitude=float(latitude) if latitude else None,
                    longitude=float(longitude) if longitude else None
                )
                
            log_action(request.user, f"Created Warehouse: {warehouse.name}")
            
            serializer = WarehouseSerializer(warehouse)
            return Response({'message': 'Warehouse created successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating warehouse: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while creating the warehouse.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateProductAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'You do not belong to a valid company.'}, status=status.HTTP_403_FORBIDDEN)
            
        name = request.data.get('name')
        sku = request.data.get('sku')
        description = request.data.get('description', '')
        
        if not name or not sku:
            return Response({'error': 'Product name and SKU are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                # Lock company row
                company = Company.objects.select_for_update().get(company_id=company.company_id)
                
                if Product.objects.filter(company=company, sku__iexact=sku).exists():
                    return Response({'error': 'A product with this SKU already exists.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                product = Product.objects.create(
                    company=company,
                    name=name,
                    sku=sku,
                    description=description
                )
                
            log_action(request.user, f"Created Product: {product.name} (SKU: {product.sku})")
            
            serializer = ProductSerializer(product)
            return Response({'message': 'Product created successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while creating the product.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateStockAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Increase or decrease stock quantity for a product in a warehouse."""
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'You do not belong to a valid company.'}, status=status.HTTP_403_FORBIDDEN)
            
        warehouse_id = request.data.get('warehouse_id')
        product_id = request.data.get('product_id')
        quantity_change = request.data.get('quantity_change') # positive to add, negative to remove
        
        if not warehouse_id or not product_id or quantity_change is None:
            return Response({'error': 'warehouse_id, product_id, and quantity_change are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            quantity_change = int(quantity_change)
        except ValueError:
            return Response({'error': 'quantity_change must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                # Verify ownership — only lock the WarehouseStock row, not Warehouse/Product
                # PR-002: Removed select_for_update on Warehouse and Product to avoid
                # serializing all inventory operations across the entire company
                warehouse = Warehouse.objects.get(id=warehouse_id, company=company)
                product = Product.objects.get(id=product_id, company=company)
                
                from django.db import IntegrityError
                try:
                    stock = WarehouseStock.objects.select_for_update().get(warehouse=warehouse, product=product)
                except WarehouseStock.DoesNotExist:
                    try:
                        stock = WarehouseStock.objects.create(
                            warehouse=warehouse,
                            product=product,
                            stock_quantity=0
                        )
                    except IntegrityError:
                        # Another transaction created it just before we did
                        stock = WarehouseStock.objects.select_for_update().get(warehouse=warehouse, product=product)
                
                new_quantity = stock.stock_quantity + quantity_change
                if new_quantity < 0:
                     return Response({'error': f'Cannot reduce stock below 0. Current stock is {stock.stock_quantity}.'}, status=status.HTTP_400_BAD_REQUEST)
                
                stock.stock_quantity = new_quantity
                stock.save()
                
                action_text = f"Added {quantity_change} units" if quantity_change > 0 else f"Deducted {abs(quantity_change)} units"
                from .models import InventoryLog
                InventoryLog.objects.create(
                    company=company,
                    user_name=get_display_name(request.user),
                    product_name=product.name,
                    warehouse_name=warehouse.name,
                    action=f"{action_text} (Total: {new_quantity})"
                )
                
                log_action(request.user, f"Updated Stock for {product.name} at {warehouse.name} to {new_quantity}")
                
                serializer = WarehouseStockSerializer(stock)
                return Response({'message': 'Stock updated successfully!', 'data': serializer.data}, status=status.HTTP_200_OK)
                
        except (Warehouse.DoesNotExist, Product.DoesNotExist):
            return Response({'error': 'Warehouse or Product not found, or does not belong to your company.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating stock: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while updating the stock.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetStockAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Fetch available stock quantity for a product in a warehouse."""
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'You do not belong to a valid company.'}, status=status.HTTP_403_FORBIDDEN)
            
        warehouse_id = request.query_params.get('warehouse_id')
        product_id = request.query_params.get('product_id')
        
        if not warehouse_id or not product_id:
            return Response({'error': 'warehouse_id and product_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            stock = WarehouseStock.objects.get(
                warehouse__id=warehouse_id, 
                warehouse__company=company,
                product__id=product_id, 
                product__company=company
            )
            return Response({'stock_quantity': stock.stock_quantity}, status=status.HTTP_200_OK)
        except WarehouseStock.DoesNotExist:
            return Response({'stock_quantity': 0}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Get Stock Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while fetching stock.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from operations.models import OrderItem

class DeleteWarehouseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        warehouse_id = request.data.get('warehouse_id')
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id, company=company)
            # Check for linked orders/shipments
            if OrderItem.objects.filter(warehouse=warehouse).exists():
                return Response({'error': 'Cannot delete warehouse because it is linked to existing orders or shipments.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # DIR-001: Prevent cascading deletion of inventory data
            if WarehouseStock.objects.filter(warehouse=warehouse, stock_quantity__gt=0).exists():
                return Response({'error': 'Cannot delete warehouse with non-zero stock. Please zero out all inventory first.'}, status=status.HTTP_400_BAD_REQUEST)
                
            warehouse.delete()
            log_action(request.user, f"Deleted Warehouse: {warehouse.name}")
            return Response({'message': 'Warehouse deleted successfully.'}, status=status.HTTP_200_OK)
        except Warehouse.DoesNotExist:
            return Response({'error': 'Warehouse not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Delete Warehouse Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while deleting the warehouse.'}, status=status.HTTP_400_BAD_REQUEST)

class DeleteProductAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        product_id = request.data.get('product_id')
        try:
            product = Product.objects.get(id=product_id, company=company)
            # Check for linked orders
            if OrderItem.objects.filter(product=product).exists():
                return Response({'error': 'Cannot delete product because it is linked to existing orders or shipments.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # DIR-001: Prevent cascading deletion of inventory data
            if WarehouseStock.objects.filter(product=product, stock_quantity__gt=0).exists():
                return Response({'error': 'Cannot delete product with non-zero stock. Please zero out all inventory first.'}, status=status.HTTP_400_BAD_REQUEST)
                
            product.delete()
            log_action(request.user, f"Deleted Product: {product.name}")
            return Response({'message': 'Product deleted successfully.'}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Delete Product Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while deleting the product.'}, status=status.HTTP_400_BAD_REQUEST)

class UpdateWarehouseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        warehouse_id = request.data.get('warehouse_id')
        name = request.data.get('name')
        location = request.data.get('location')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id, company=company)
            # BUG-003: Validate name uniqueness before saving
            if name and name != warehouse.name:
                if Warehouse.objects.filter(company=company, name__iexact=name).exclude(id=warehouse.id).exists():
                    return Response({'error': 'A warehouse with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
                warehouse.name = name
            if location: warehouse.location = location
            if latitude: warehouse.latitude = float(latitude)
            if longitude: warehouse.longitude = float(longitude)
            
            warehouse.save()
            log_action(request.user, f"Updated Warehouse: {warehouse.name}")
            return Response({'message': 'Warehouse updated successfully.'}, status=status.HTTP_200_OK)
        except Warehouse.DoesNotExist:
            return Response({'error': 'Warehouse not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Update Warehouse Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while updating the warehouse.'}, status=status.HTTP_400_BAD_REQUEST)

class UpdateProductAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        company = get_user_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        product_id = request.data.get('product_id')
        name = request.data.get('name')
        sku = request.data.get('sku')
        description = request.data.get('description')
        
        try:
            product = Product.objects.get(id=product_id, company=company)
            
            if sku and sku != product.sku:
                if Product.objects.filter(company=company, sku__iexact=sku).exclude(id=product.id).exists():
                    return Response({'error': 'A product with this SKU already exists.'}, status=status.HTTP_400_BAD_REQUEST)
                product.sku = sku
                
            if name: product.name = name
            if description is not None: product.description = description
            
            product.save()
            log_action(request.user, f"Updated Product: {product.name}")
            return Response({'message': 'Product updated successfully.'}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Update Product Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while updating the product.'}, status=status.HTTP_400_BAD_REQUEST)
