from django.urls import path
from . import views

urlpatterns = [
    path('invite/<uuid:token>/', views.manager_invite, name='manager_invite'),
    # For audit logs, we can just put it under b2b_admin routes, but let's keep it here if needed
]
