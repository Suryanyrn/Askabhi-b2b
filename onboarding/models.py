import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password

class Company(models.Model):
    company_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.OneToOneField(User, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    company_name = models.CharField(max_length=200)
    company_email = models.EmailField(unique=True)
    
    # Address Fields
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    pincode = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    village_or_city = models.CharField(max_length=100)

    def __str__(self):
        return self.company_name