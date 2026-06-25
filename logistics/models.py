import uuid
from django.db import models
from onboarding.models import Company

class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='warehouses')
    name = models.CharField(max_length=200)
    location = models.TextField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    class Meta:
        unique_together = ('company', 'name')
        
    def __str__(self):
        return f"{self.name} - {self.company.company_name}"

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='products')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('company', 'sku')
        
    def __str__(self):
        return f"{self.name} ({self.sku})"

class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='warehouse_stocks')
    stock_quantity = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ('warehouse', 'product')
        
    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.stock_quantity}"

class InventoryLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='inventory_logs')
    user_name = models.CharField(max_length=200, help_text="Name of the person who made the change")
    product_name = models.CharField(max_length=200)
    warehouse_name = models.CharField(max_length=200)
    action = models.CharField(max_length=255, help_text="e.g. 'Added 50 units', 'Deducted 5 units (Order #123)'")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.product_name} - {self.action} at {self.timestamp}"
