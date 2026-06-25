from rest_framework import serializers
from .models import Warehouse, Product, WarehouseStock

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'location']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'description']

class WarehouseStockSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = WarehouseStock
        fields = ['id', 'warehouse', 'warehouse_name', 'product', 'product_name', 'product_sku', 'stock_quantity']
