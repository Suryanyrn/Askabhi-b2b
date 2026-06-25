from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_onboarding, name='admin_onboarding'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
]