from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from b2b_admin.utils import get_user_role_and_company
from onboarding.utils import OTPManager
from django.core.mail import send_mail
import json

@login_required(login_url='/onboard/')
def api_profile_update(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
        
    role, company = get_user_role_and_company(request.user)
    
    if role == 'MANAGER':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        
        if not name or not phone:
            return JsonResponse({'error': 'Missing fields'}, status=400)
            
        manager = request.user.manager
        manager.name = name
        manager.phone = phone
        manager.save()
        return JsonResponse({'message': 'Profile updated successfully'}, status=200)
        
    elif role == 'ADMIN' and company:
        company_name = request.POST.get('company_name')
        if not company_name:
            return JsonResponse({'error': 'Missing fields'}, status=400)
            
        company.company_name = company_name
        company.save()
        return JsonResponse({'message': 'Company profile updated successfully'}, status=200)
        
    return JsonResponse({'error': 'Unauthorized'}, status=403)

@login_required(login_url='/onboard/')
def api_profile_send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
        
    email = request.user.email
    if not email:
        return JsonResponse({'status': 'error', 'message': 'User has no email associated'})
        
    otp_code = OTPManager.generate_otp(email)
    send_mail(
        'Your Password Reset OTP',
        f'Your OTP is: {otp_code}',
        None,
        [email],
        fail_silently=False,
    )
    
    return JsonResponse({'status': 'success', 'message': 'OTP sent to your email.'})

@login_required(login_url='/onboard/')
def api_profile_verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'})
        
    email = request.user.email
    otp = request.POST.get('otp')
    
    if not otp:
        return JsonResponse({'status': 'error', 'message': 'OTP required'})
        
    is_valid, msg = OTPManager.verify_otp(email, otp)
    if is_valid:
        # We store a session flag that they are verified to change password
        request.session['pwd_otp_verified'] = True
        return JsonResponse({'status': 'success', 'message': 'OTP verified.'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP.'})

@login_required(login_url='/onboard/')
def api_profile_change_password(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
        
    if not request.session.get('pwd_otp_verified'):
        return JsonResponse({'error': 'OTP not verified'}, status=403)
        
    password = request.POST.get('password')
    confirm_password = request.POST.get('confirm_password')
    
    if not password or password != confirm_password:
        return JsonResponse({'error': 'Passwords do not match or are empty'}, status=400)
        
    import re
    if not re.match(r'^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]).{8,}$', password):
        return JsonResponse({'error': 'Password does not meet requirements.'}, status=400)
        
    user = request.user
    user.set_password(password)
    user.save()
    
    # Keep the user logged in after password change
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, user)
    
    # Clear the verification flag
    del request.session['pwd_otp_verified']
    
    return JsonResponse({'message': 'Password updated successfully'}, status=200)
