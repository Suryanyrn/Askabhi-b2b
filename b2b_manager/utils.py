from .models import AuditLog
from b2b_admin.utils import get_user_role_and_company

def log_action(user, action_desc):
    role, company = get_user_role_and_company(user)
    if not company:
        return
        
    user_name = "Unknown"
    if role == 'ADMIN':
        user_name = f"{company.company_name} (Admin)"
    elif role == 'MANAGER':
        # Safely get manager name
        if hasattr(user, 'manager'):
            user_name = user.manager.name
        else:
            user_name = "Manager"
        
    AuditLog.objects.create(
        company=company,
        user=user,
        user_name=user_name,
        role=role,
        action=action_desc
    )
