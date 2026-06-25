from django.shortcuts import render, get_object_or_404
from .models import Shipment

def client_tracking_view(request, shipment_id):
    """Public read-only view for a client to track their shipment."""
    # We use the UUID as the ID since it is unpredictable
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    context = {
        'shipment': shipment,
        'order': shipment.order,
        'client': shipment.order.client,
        'company': shipment.order.company
    }
    return render(request, 'operations/client_tracking.html', context)
