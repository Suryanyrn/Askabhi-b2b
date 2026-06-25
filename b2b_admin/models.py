import uuid
from django.db import models
from django.contrib.auth.models import User
from onboarding.models import Company

class Manager(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='managers')
    user = models.OneToOneField(User, on_delete=models.PROTECT, null=True, blank=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(null=True, blank=True)
    team = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20)
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    
    class Meta:
        unique_together = (('company', 'phone'), ('company', 'email'))
        
    def __str__(self):
        return f"{self.name} - {self.company.company_name}"

class Driver(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='drivers')
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    license_id = models.CharField(max_length=100, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    is_first_login = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('company', 'phone')
        
    def __str__(self):
        return f"{self.name} - {self.company.company_name}"

class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='clients')
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = (('company', 'phone'), ('company', 'email'))
        
    def __str__(self):
        return f"{self.name} - {self.company.company_name}"
