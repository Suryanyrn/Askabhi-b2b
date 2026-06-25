from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from b2b_admin.models import Manager, Driver

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        role = 'UNKNOWN'
        company_id = None
        name = user.email

        if hasattr(user, 'company'):
            role = 'ADMIN'
            company_id = str(user.company.company_id)
            name = user.company.company_name
        elif Manager.objects.filter(user=user).exists():
            role = 'MANAGER'
            manager = Manager.objects.get(user=user)
            company_id = str(manager.company.company_id)
            name = manager.name
        elif Driver.objects.filter(user=user).exists():
            role = 'DRIVER'
            driver = Driver.objects.get(user=user)
            company_id = str(driver.company.company_id)
            name = driver.name

        token['role'] = role
        token['company_id'] = company_id
        token['name'] = name
        token['email'] = user.email
        
        return token
