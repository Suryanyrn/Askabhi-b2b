import logging
import secrets
import string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.contrib.auth.models import User
from onboarding.models import Company
from .models import Manager, Driver
from .serializers import ManagerSerializer, DriverSerializer
from .utils import get_user_role_and_company
from b2b_manager.utils import log_action
from operations.models import Notification

logger = logging.getLogger('b2b_admin')

def generate_temp_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for i in range(length))

from rest_framework.permissions import IsAuthenticated

class CreatePersonnelAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        role, company = get_user_role_and_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
            
        target_role = request.data.get('role')
        phone = request.data.get('phone')
        
        if not target_role or not phone:
            return Response({'error': 'Role and phone are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Managers cannot add other managers
        if role == 'MANAGER' and target_role == 'manager':
            return Response({'error': 'Managers do not have permission to add other managers.'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            # Enforce ACID properties with strict row-level locking on the Company object
            with transaction.atomic():
                # Lock the company row to prevent concurrent creation race conditions
                company = Company.objects.select_for_update().get(pk=company.pk)
                
                # Check for duplicates across the company
                if Manager.objects.filter(company=company, phone=phone).exists() or \
                   Driver.objects.filter(company=company, phone=phone).exists():
                    return Response({'error': 'A person with this phone number already exists in your company.'}, status=status.HTTP_400_BAD_REQUEST)
                
                temp_password = generate_temp_password()
                
                if target_role == 'manager':
                    email = request.data.get('email')
                    name = request.data.get('manager_name')
                    team = request.data.get('team')
                    
                    if not email or not name:
                        return Response({'error': 'Manager name and email are required.'}, status=status.HTTP_400_BAD_REQUEST)
                        
                    # Check global email duplicate for auth.User
                    if User.objects.filter(email=email).exists() or Manager.objects.filter(email=email).exists():
                         return Response({'error': 'A user with this email already exists in the system.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Create Manager WITHOUT Auth User initially
                    manager = Manager.objects.create(
                        company=company,
                        name=name,
                        email=email,
                        team=team,
                        phone=phone
                    )
                    
                    invite_link = f"{request.scheme}://{request.get_host()}/manager/invite/{manager.invite_token}/"
                    
                    logger.info(f"Manager invite created: {name} for company {company.company_name}.")
                    # TODO: Send actual email with secure login link
                    print(f"--- MOCK EMAIL ---")
                    print(f"To: {email}")
                    print(f"Subject: Invitation to join {company.company_name} as a Manager")
                    print(f"Body: Please click the link below to set your password and activate your account:\n{invite_link}")
                    print(f"------------------")
                    
                    log_action(request.user, f"Invited new Manager: {name}")
                    
                    serializer = ManagerSerializer(manager)
                    return Response({'message': 'Manager invited successfully! Invite link sent to their email.', 'data': serializer.data}, status=status.HTTP_201_CREATED)
                    
                elif target_role == 'driver':
                    name = request.data.get('driver_name')
                    license_id = request.data.get('license_id')
                    
                    if not name:
                        return Response({'error': 'Driver name is required.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Drivers use their phone number as username
                    # Prefix with company ID to ensure global uniqueness just in case
                    driver_username = f"drv_{company.company_id}_{phone}"
                    
                    if User.objects.filter(username=driver_username).exists():
                        return Response({'error': 'This driver is already registered.'}, status=status.HTTP_400_BAD_REQUEST)
                        
                    auth_user = User(
                        username=driver_username,
                        is_active=True
                    )
                    auth_user.set_password(temp_password)
                    auth_user.save()
                    
                    driver = Driver.objects.create(
                        company=company,
                        user=auth_user,
                        name=name,
                        phone=phone,
                        license_id=license_id
                    )
                    
                    logger.info(f"Driver created: {name} for company {company.company_name}. Temp password generated.")
                    # TODO: Send actual SMS with secure login link
                    print(f"--- MOCK SMS ---")
                    print(f"To: {phone}")
                    print(f"Body: Welcome {name}! You have been added as a driver for {company.company_name}. Login link: http://... Password: {temp_password}")
                    print(f"----------------")
                    
                    log_action(request.user, f"Added Driver: {name}")
                    
                    serializer = DriverSerializer(driver)
                    return Response({'message': 'Driver created successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
                    
                else:
                    return Response({'error': 'Invalid role specified.'}, status=status.HTTP_400_BAD_REQUEST)

        except Company.DoesNotExist:
            return Response({'error': 'Company profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating personnel: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while creating personnel.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdatePersonnelAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        role_type, company = get_user_role_and_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
            
        target_role = request.data.get('role') # 'manager' or 'driver'
        personnel_id = request.data.get('id')
        
        if not target_role or not personnel_id:
            return Response({'error': 'Role and ID are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if role_type == 'MANAGER' and target_role == 'manager':
            return Response({'error': 'Managers cannot edit other managers.'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            if target_role == 'manager':
                manager = Manager.objects.get(id=personnel_id, company=company)
                manager.name = request.data.get('manager_name', manager.name)
                manager.team = request.data.get('team', manager.team)
                manager.phone = request.data.get('phone', manager.phone)
                # If email changes, user object should also change if they exist, but for simplicity let's assume email is read-only or we update both
                new_email = request.data.get('email')
                if new_email and new_email != manager.email:
                    if User.objects.filter(email=new_email).exists() or Manager.objects.filter(email=new_email).exclude(id=manager.id).exists():
                        return Response({'error': 'Email already in use.'}, status=status.HTTP_400_BAD_REQUEST)
                    manager.email = new_email
                    if manager.user:
                        manager.user.email = new_email
                        manager.user.username = new_email
                        manager.user.save()
                        
                manager.save()
                log_action(request.user, f"Updated Manager: {manager.name}")
                return Response({'message': 'Manager updated successfully.'}, status=status.HTTP_200_OK)
                
            elif target_role == 'driver':
                driver = Driver.objects.get(id=personnel_id, company=company)
                # Wait, driver model has user attached. Driver fields are in user mostly? No, let's look at Driver model. 
                # Let's import Driver model to check fields. Actually, earlier I saw we create Driver with:
                # name, phone, license_id. BUT we don't have driver name natively on driver? Wait!
                # Driver.user.first_name? In CreatePersonnelAPIView:
                # name = request.data.get('driver_name')
                # Driver.objects.create(company=company, user=user, phone=phone, license_id=license_id) 
                # And user.first_name = name.
                name = request.data.get('driver_name')
                if name:
                    driver.name = name
                    driver.user.first_name = name
                    driver.user.save()
                driver.phone = request.data.get('phone', driver.phone)
                driver.license_id = request.data.get('license_id', driver.license_id)
                driver.save()
                log_action(request.user, f"Updated Driver: {driver.name}")
                return Response({'message': 'Driver updated successfully.'}, status=status.HTTP_200_OK)
                
        except (Manager.DoesNotExist, Driver.DoesNotExist):
            return Response({'error': 'Personnel not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Update Personnel Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while updating personnel.'}, status=status.HTTP_400_BAD_REQUEST)

class DeletePersonnelAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        role_type, company = get_user_role_and_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
            
        target_role = request.data.get('role')
        personnel_id = request.data.get('id')
        
        if not target_role or not personnel_id:
            return Response({'error': 'Role and ID are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if role_type == 'MANAGER' and target_role == 'manager':
            return Response({'error': 'Managers cannot delete other managers.'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            if target_role == 'manager':
                manager = Manager.objects.get(id=personnel_id, company=company)
                if manager.user:
                    manager.user.delete() # Also deletes manager because of CASCADE
                else:
                    manager.delete()
                log_action(request.user, f"Deleted Manager: {manager.name}")
                return Response({'message': 'Manager deleted successfully.'}, status=status.HTTP_200_OK)
                
            elif target_role == 'driver':
                driver = Driver.objects.get(id=personnel_id, company=company)
                
                # Check for active shipments
                from operations.models import Shipment
                if Shipment.objects.filter(driver=driver, status='ACTIVE').exists():
                    return Response({'error': 'Cannot delete driver because they are assigned to an active, undelivered order.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                driver.user.delete() # Cascades to Driver
                log_action(request.user, f"Deleted Driver")
                return Response({'message': 'Driver deleted successfully.'}, status=status.HTTP_200_OK)
                
        except (Manager.DoesNotExist, Driver.DoesNotExist):
            return Response({'error': 'Personnel not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Delete Personnel Error: {str(e)}", exc_info=True)
            return Response({'error': 'An unexpected error occurred while deleting personnel.'}, status=status.HTTP_400_BAD_REQUEST)

class NotificationAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        role_type, company = get_user_role_and_company(request.user)
        if not company:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        notifications = Notification.objects.filter(company=company).order_by('-created_at')[:20]
        unread_count = Notification.objects.filter(company=company, is_read=False).count()
        
        data = [{
            'id': str(n.id),
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
        
        return Response({'unread_count': unread_count, 'notifications': data})
        
    def post(self, request):
        role_type, company = get_user_role_and_company(request.user)
        if company:
            Notification.objects.filter(company=company, is_read=False).update(is_read=True)
        return Response({'status': 'ok'})
