from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from .models import Manager, Driver
from .utils import get_user_role_and_company
from b2b_manager.models import AuditLog
from django.http import HttpResponse
from operations.models import Order, Shipment
from b2b_admin.models import Client
from logistics.models import Warehouse, Product, WarehouseStock
from django.db.models import Sum

def health(request):
    return HttpResponse("inga onnum illai vera pakam po")

@login_required(login_url='/onboard/')
def dashboard_home(request):
    """
    Main entry point for the company admin dashboard.
    Only accessible by logged-in users.
    """
    role, company = get_user_role_and_company(request.user)
    
    if company:
        total_orders = Order.objects.filter(company=company).count()
        total_clients = Client.objects.filter(company=company).count()
        total_managers = Manager.objects.filter(company=company).count()
        # Combine Driver queries into a single database hit
        all_drivers = list(Driver.objects.filter(company=company))
        total_drivers = len(all_drivers)
        available_drivers = [d for d in all_drivers if d.is_available]
        duty_drivers = [d for d in all_drivers if not d.is_available]
        
        active_shipments = Shipment.objects.filter(order__company=company, status='ACTIVE').count()
        
        total_warehouses = Warehouse.objects.filter(company=company).count()
        total_products = Product.objects.filter(company=company).count()
    else:
        total_orders = total_clients = total_managers = total_drivers = active_shipments = 0
        total_warehouses = total_products = 0
        available_drivers = []
        duty_drivers = []
        
    context = {
        'company': company,
        'role': role,
        'total_orders': total_orders,
        'total_clients': total_clients,
        'total_managers': total_managers,
        'total_drivers': total_drivers,
        'active_shipments': active_shipments,
        'total_warehouses': total_warehouses,
        'total_products': total_products,
        'available_drivers': available_drivers,
        'duty_drivers': duty_drivers,
    }
    return render(request, 'b2b_admin/dashboard.html', context)

@login_required(login_url='/onboard/')
def managers_list(request):
    """View to list all managers for the company."""
    role, company = get_user_role_and_company(request.user)
    managers = Manager.objects.filter(company=company) if company else []
    
    context = {
        'company': company,
        'role': role,
        'managers': managers
    }
    return render(request, 'b2b_admin/managers_list.html', context)

@login_required(login_url='/onboard/')
def drivers_list(request):
    """View to list all drivers for the company."""
    role, company = get_user_role_and_company(request.user)
    
    if company:
        drivers = Driver.objects.filter(company=company)
    else:
        drivers = []
        
    context = {
        'company': company,
        'role': role,
        'drivers': drivers,
    }
    return render(request, 'b2b_admin/drivers_list.html', context)

@login_required(login_url='/onboard/')
def driver_profile_view(request, driver_id):
    """View a specific driver's profile and their delivery history."""
    role, company = get_user_role_and_company(request.user)
    
    if not company:
        return redirect('admin_dashboard')
        
    driver = get_object_or_404(Driver, id=driver_id, company=company)
    completed_shipments = Shipment.objects.filter(
        driver=driver,
        status__in=['PENDING_APPROVAL', 'COMPLETED']
    ).order_by('-completed_at', '-id')
    
    context = {
        'company': company,
        'role': role,
        'driver': driver,
        'completed_shipments': completed_shipments,
    }
    return render(request, 'b2b_admin/driver_profile.html', context)

@login_required(login_url='/onboard/')
def warehouse_list(request):
    """View to list all warehouses for the company."""
    role, company = get_user_role_and_company(request.user)
    if company:
        warehouses = Warehouse.objects.filter(company=company).prefetch_related(
            'inventory__product'
        )
        products = Product.objects.filter(company=company)
    else:
        warehouses = []
        products = []
    
    context = {
        'company': company,
        'role': role,
        'warehouses': warehouses,
        'products': products,
    }
    return render(request, 'b2b_admin/warehouse_list.html', context)

@login_required(login_url='/onboard/')
def products_list(request):
    """View to list all products for the company with stock details."""
    role, company = get_user_role_and_company(request.user)
    
    if company:
        products = Product.objects.filter(company=company).annotate(
            total_stock=Sum('warehouse_stocks__stock_quantity')
        ).prefetch_related('warehouse_stocks__warehouse')
        warehouses = Warehouse.objects.filter(company=company)
    else:
        products = []
        warehouses = []
    
    context = {
        'company': company,
        'role': role,
        'products': products,
        'warehouses': warehouses,
    }
    return render(request, 'b2b_admin/products_list.html', context)

from operations.models import Order
from b2b_admin.models import Client

@login_required(login_url='/onboard/')
def orders_list(request):
    """View to list all orders and create new ones."""
    role, company = get_user_role_and_company(request.user)
    
    if company:
        orders_query = Order.objects.filter(company=company).exclude(status='DELIVERED').order_by('-created_at').select_related('client', 'shipment', 'shipment__driver').prefetch_related('items__product', 'items__warehouse')
        from django.core.paginator import Paginator
        paginator = Paginator(orders_query, 20)
        page_number = request.GET.get('page')
        orders = paginator.get_page(page_number)
        clients = Client.objects.filter(company=company)
        warehouses = Warehouse.objects.filter(company=company).prefetch_related('inventory__product')
        products = Product.objects.filter(company=company)
        available_drivers = Driver.objects.filter(company=company, is_available=True)
    else:
        orders = []
        clients = []
        warehouses = []
        products = []
        available_drivers = []
        
    context = {
        'company': company,
        'role': role,
        'orders': orders,
        'clients': clients,
        'warehouses': warehouses,
        'products': products,
        'available_drivers': available_drivers,
    }
    return render(request, 'b2b_admin/orders_list.html', context)

from operations.models import Shipment

@login_required(login_url='/onboard/')
def shipments_list(request):
    """View to list active shipments with live tracking."""
    role, company = get_user_role_and_company(request.user)
    
    if company:
        shipments = Shipment.objects.filter(
            order__company=company, 
            status__in=['ACTIVE', 'IN_TRANSIT', 'PENDING_APPROVAL']
        ).select_related('order', 'order__client', 'driver').prefetch_related('order__items__warehouse')
    else:
        shipments = []
        
    context = {
        'company': company,
        'role': role,
        'shipments': shipments,
    }
    return render(request, 'b2b_admin/shipments_list.html', context)

from django.db.models import Count

@login_required(login_url='/onboard/')
def clients_list(request):
    """View to list all clients with their order history."""
    role, company = get_user_role_and_company(request.user)
    
    if company:
        clients = Client.objects.filter(company=company).annotate(total_orders=Count('orders')).order_by('-total_orders')
    else:
        clients = []
        
    context = {
        'company': company,
        'role': role,
        'clients': clients,
    }
    return render(request, 'b2b_admin/clients_list.html', context)

def logout_user(request):
    """Logs out the user and redirects to the onboarding page."""
    if request.method == 'POST':
        logout(request)
    return redirect('admin_onboarding')

from django.core.paginator import Paginator
from datetime import datetime

@login_required(login_url='/onboard/')
def audit_logs_list(request):
    role, company = get_user_role_and_company(request.user)
    audit_logs = AuditLog.objects.filter(company=company) if company else AuditLog.objects.none()
    
    # Date Filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            audit_logs = audit_logs.filter(timestamp__gte=datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if end_date:
        try:
            # Add 1 day to include the entire end_date
            from datetime import timedelta
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            audit_logs = audit_logs.filter(timestamp__lt=end)
        except ValueError:
            pass
            
    # Pagination
    per_page = request.GET.get('per_page', '10')
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
        
    paginator = Paginator(audit_logs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'company': company,
        'role': role,
        'page_obj': page_obj,
        'per_page': per_page,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'b2b_admin/audit_list.html', context)

@login_required
def previous_orders_list(request):
    role_type, company = get_user_role_and_company(request.user)
    if not company:
        return redirect('dashboard_home')
        
    # Only show delivered orders here
    orders = Order.objects.filter(company=company, status='DELIVERED').order_by('-created_at').select_related('client', 'shipment', 'shipment__driver').prefetch_related('items__product', 'items__warehouse')
    
    # Date Filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            orders = orders.filter(created_at__gte=datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if end_date:
        try:
            from datetime import timedelta
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            orders = orders.filter(created_at__lt=end)
        except ValueError:
            pass
    
    # Search filtering
    search_query = request.GET.get('q', '').strip()
    if search_query:
        from django.db.models import Q
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(client__name__icontains=search_query) |
            Q(shipment__driver__name__icontains=search_query)
        )
    
    # Pagination
    per_page = request.GET.get('per_page', '10')
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
        
    paginator = Paginator(orders, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'role': role_type,
        'company': company,
        'page_obj': page_obj,
        'per_page': per_page,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
    }
    return render(request, 'b2b_admin/previous_orders.html', context)

from logistics.models import InventoryLog

@login_required(login_url='/onboard/')
def inventory_logs_list(request):
    role, company = get_user_role_and_company(request.user)
    inv_logs = InventoryLog.objects.filter(company=company) if company else InventoryLog.objects.none()
    
    # Date Filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            inv_logs = inv_logs.filter(timestamp__gte=datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass
    if end_date:
        try:
            from datetime import timedelta
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            inv_logs = inv_logs.filter(timestamp__lt=end)
        except ValueError:
            pass
            
    # Pagination
    per_page = request.GET.get('per_page', '10')
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
        
    paginator = Paginator(inv_logs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'company': company,
        'role': role,
        'page_obj': page_obj,
        'per_page': per_page,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'b2b_admin/inventory_logs.html', context)

