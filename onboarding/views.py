from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction # IMPORT THIS
from django.http import JsonResponse
from django.core.mail import send_mail
from .models import Company
from b2b_admin.models import Manager, Driver, Client
from .utils import OTPManager
import logging

logger = logging.getLogger('onboarding')

def landing_page(request):
    companies_count = Company.objects.count()
    managers_count = Manager.objects.count()
    clients_count = Client.objects.count()
    drivers_count = Driver.objects.count()
    
    context = {
        'companies_count': companies_count,
        'managers_count': managers_count,
        'clients_count': clients_count,
        'drivers_count': drivers_count,
    }
    return render(request, 'landing.html', context)

def admin_onboarding(request):
    # If the user is already logged in, send them straight to the dashboard
    if request.user.is_authenticated:
        return redirect('dashboard_home')
        
    if request.method == 'POST':
        
        # --- Handle Login ---
        if 'login_email' in request.POST:
            email = request.POST.get('login_email')
            password = request.POST.get('login_password')
            
            # Use Django's built-in authentication against the User model
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, "Login successful!")
                logger.info(f"User {email} logged in successfully.")
                return redirect('dashboard_home')
            else:
                messages.error(request, "Invalid email or password.")
                logger.warning(f"Failed login attempt for {email}.")
            return redirect('admin_onboarding')

        # --- Handle Onboarding ---
        company_name = request.POST.get('company_name')
        company_email = request.POST.get('company_email')
        password = request.POST.get('password')
        
        # Domain Validation
        free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        domain = company_email.split('@')[1].lower() if '@' in company_email else ""
        
        if domain in free_domains:
            messages.error(request, "Please use a valid company domain email.")
            return redirect('admin_onboarding')
            
        if request.session.get('verified_email') != company_email:
            messages.error(request, "Email verification is required before onboarding.")
            return redirect('admin_onboarding')
            
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('admin_onboarding')

        user_qs = User.objects.filter(email=company_email)
        if user_qs.exists():
            existing_user = user_qs.first()
            if hasattr(existing_user, 'company'):
                messages.error(request, "Email already registered.")
                return redirect('admin_onboarding')
            else:
                # Orphaned user from a previously failed onboarding, delete it
                existing_user.delete()

        # ALL-OR-NOTHING DATABASE SAVE
        try:
            with transaction.atomic():
                # 1. Create the Auth User
                user = User.objects.create_user(
                    username=company_email, 
                    email=company_email, 
                    password=password, 
                    is_active=True
                )
                
                # 2. Create the Company
                Company.objects.create(
                    admin_user=user,
                    company_name=company_name,
                    company_email=company_email,
                    address_line_1=request.POST.get('address_line_1'),
                    address_line_2=request.POST.get('address_line_2'),
                    pincode=request.POST.get('pincode'),
                    country=request.POST.get('country', 'India'),
                    state=request.POST.get('state'),
                    district=request.POST.get('district'),
                    village_or_city=request.POST.get('village_or_city')
                )
            
            messages.success(request, "Onboarding successful! You can now log in.")
            logger.info(f"Company onboarding successful for {company_email}.")
            if 'verified_email' in request.session:
                del request.session['verified_email']
        except Exception as e:
            # If ANYTHING fails (like a missing field), it rolls back and shows an error
            messages.error(request, f"An error occurred: {str(e)}")
            logger.error(f"Error during onboarding for {company_email}: {str(e)}")
            
        return redirect('admin_onboarding') 

    return render(request, 'admin_onboard.html')

def send_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if not email:
            return JsonResponse({'status': 'error', 'message': 'Email is required.'}, status=400)
            
        free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        domain = email.split('@')[1].lower() if '@' in email else ""
        if domain in free_domains:
            return JsonResponse({'status': 'error', 'message': 'Please use a valid company domain email.'}, status=400)
            
        if User.objects.filter(email=email).exists():
            user_obj = User.objects.filter(email=email).first()
            if hasattr(user_obj, 'company'):
                return JsonResponse({'status': 'error', 'message': 'Email already registered.'}, status=400)
            
        otp = OTPManager.generate_otp(email)
        
        # Send email
        subject = 'Your Verification OTP - B2B Tracking Portal'
        message = f'Your One-Time Password for company onboarding is: {otp}\n\nThis OTP is valid for 5 minutes.'
        from_email = 'no-reply@b2bportal.com'
        recipient_list = [email]
        
        try:
            send_mail(subject, message, from_email, recipient_list)
            logger.info(f"OTP sent successfully to {email}.")
            return JsonResponse({'status': 'success', 'message': 'OTP sent successfully to ' + email})
        except Exception as e:
            logger.error(f"Failed to send OTP to {email}: {str(e)}")
            return JsonResponse({'status': 'error', 'message': f'Failed to send email: {str(e)}'}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

def verify_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp = request.POST.get('otp')
        
        if not email or not otp:
            return JsonResponse({'status': 'error', 'message': 'Email and OTP are required.'}, status=400)
            
        is_valid, message = OTPManager.verify_otp(email, otp)
        
        if is_valid:
            logger.info(f"OTP verified successfully for {email}.")
            request.session['verified_email'] = email
            return JsonResponse({'status': 'success', 'message': message})
        else:
            logger.warning(f"OTP verification failed for {email}: {message}")
            return JsonResponse({'status': 'error', 'message': message}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)