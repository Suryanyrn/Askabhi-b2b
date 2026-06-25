from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from b2b_admin.models import Driver
from operations.models import Shipment

def driver_login_view(request):
    if request.user.is_authenticated:
        # Check if they are a driver
        try:
            Driver.objects.get(user=request.user)
            return redirect('driver_dashboard')
        except Driver.DoesNotExist:
            pass # Let them view the login page or handle appropriately

    if request.method == 'POST':
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        
        # In our system, the driver username is saved as drv_{company_id}_{phone}
        # We can find the correct username by looking up the Driver by phone
        drivers = Driver.objects.filter(phone=mobile)
        user = None
        for driver in drivers:
            user = authenticate(request, username=driver.user.username, password=password)
            if user is not None:
                break
            
        if user is not None:
            try:
                # Ensure they are actually a driver
                Driver.objects.get(user=user)
                login(request, user)
                
                # Check if it's their first login
                driver_obj = Driver.objects.get(user=user)
                if driver_obj.is_first_login:
                    return redirect('driver_set_password')
                    
                return redirect('driver_dashboard')
            except Driver.DoesNotExist:
                messages.error(request, 'This account is not registered as a driver.')
        else:
            messages.error(request, 'Invalid mobile number or password.')
            
    return render(request, 'b2b_driver/login.html')

from django.views.decorators.http import require_POST

@require_POST
def driver_logout_view(request):
    logout(request)
    return redirect('driver_login')

@login_required
def driver_dashboard_view(request):
    try:
        driver = Driver.objects.get(user=request.user)
    except Driver.DoesNotExist:
        logout(request)
        return redirect('driver_login')
        
    # Get active or in-transit shipment
    shipment = Shipment.objects.filter(
        driver=driver, 
        status__in=['ACTIVE', 'IN_TRANSIT']
    ).first()
    
    # Get previous deliveries
    completed_shipments = Shipment.objects.filter(
        driver=driver,
        status__in=['PENDING_APPROVAL', 'COMPLETED']
    ).order_by('-completed_at', '-id')
    
    context = {
        'driver': driver,
        'shipment': shipment,
        'completed_shipments': completed_shipments,
    }
    return render(request, 'b2b_driver/dashboard.html', context)

@login_required
def driver_set_password_view(request):
    try:
        driver = Driver.objects.get(user=request.user)
    except Driver.DoesNotExist:
        logout(request)
        return redirect('driver_login')
        
    if not driver.is_first_login:
        return redirect('driver_dashboard')
        
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not password or password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        else:
            import re
            if not re.match(r'^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]).{8,}$', password):
                messages.error(request, 'Password must contain at least 8 characters, one uppercase, one number, and one special character.')
            else:
                user = request.user
                user.set_password(password)
                user.save()
                
                # Keep them logged in
                from django.contrib.auth import update_session_auth_hash
                # Remove first login flag
                driver.is_first_login = False
                driver.save()
                
                # Send Notification
                from operations.models import Notification
                Notification.objects.create(
                    company=driver.company,
                    message=f"Driver {driver.name} has completed their first login and is active."
                )
                
                # Re-authenticate the user with the new password
                user = authenticate(username=request.user.username, password=password)
                if user:
                    login(request, user)
                    
                messages.success(request, "Password set successfully!")
                return redirect('driver_dashboard')
                
    return render(request, 'b2b_driver/set_password.html')
