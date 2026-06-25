from .models import Manager
from onboarding.models import Company

def get_user_role_and_company(user):
    if hasattr(user, 'company'):
        return 'ADMIN', user.company
    
    manager = Manager.objects.filter(user=user).first()
    if manager:
        return 'MANAGER', manager.company
        
    return None, None

def get_user_company(user):
    """Convenience wrapper around get_user_role_and_company that just returns the company."""
    return get_user_role_and_company(user)[1]

def get_display_name(user):
    """Resolve a user to their proper display name for logs.
    ADMIN -> 'CompanyName (Admin)'
    MANAGER -> manager.name
    Fallback -> user.username
    """
    role, company = get_user_role_and_company(user)
    if role == 'ADMIN' and company:
        return f"{company.company_name} (Admin)"
    elif role == 'MANAGER':
        if hasattr(user, 'manager'):
            return user.manager.name
        return "Manager"
    return user.first_name or user.username

