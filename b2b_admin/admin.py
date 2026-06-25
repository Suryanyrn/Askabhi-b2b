from django.contrib import admin
from .models import Manager, Driver, Client
# Register your models here.

admin.site.register(Manager)
admin.site.register(Driver)
admin.site.register(Client)