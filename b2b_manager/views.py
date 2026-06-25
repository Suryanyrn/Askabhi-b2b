from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import login
from b2b_admin.models import Manager
from django.contrib import messages

from django.http import HttpResponseForbidden
from django.core.cache import cache

def manager_invite(request, token):
    ip = request.META.get('REMOTE_ADDR', '')
    cache_key = f"invite_rl_{ip}"
    attempts = cache.get(cache_key, 0)
    
    if attempts >= 20:
        return HttpResponseForbidden("Too many attempts. Please try again later.")
        
    cache.set(cache_key, attempts + 1, timeout=300)
    
    manager = get_object_or_404(Manager, invite_token=token)
    
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'b2b_manager/invite.html', {'manager': manager})
            
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return render(request, 'b2b_manager/invite.html', {'manager': manager})
            
        if User.objects.filter(email=manager.email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, 'b2b_manager/invite.html', {'manager': manager})
            
        # Create user
        user = User.objects.create_user(
            username=manager.email,
            email=manager.email,
            password=password
        )
        
        manager.user = user
        manager.invite_token = None
        manager.save()
        
        # Send Notification
        from operations.models import Notification
        Notification.objects.create(
            company=manager.company,
            message=f"Manager {manager.name} has completed their first login and is active."
        )
        
        # Log them in automatically and redirect to dashboard
        login(request, user)
        return redirect('dashboard_home')
        
    return render(request, 'b2b_manager/invite.html', {'manager': manager})
