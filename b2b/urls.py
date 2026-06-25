from django.contrib import admin
from django.urls import path,include
from onboarding import views as onboarding_views

urlpatterns = [
    path('', onboarding_views.landing_page, name='landing_page'),
    path('admin/', admin.site.urls),
    path('onboard/', include('onboarding.urls')),
    path('admin-panel/', include('b2b_admin.urls')),
    path('manager/', include('b2b_manager.urls')),
    path('logistics/', include('logistics.urls')),
    path('operations/', include('operations.urls')),
    path('driver/', include('b2b_driver.urls')),
    path('', include('b2b_auth.urls')),
    path('track/<uuid:shipment_id>/', include(([
        path('', __import__('operations.views').views.client_tracking_view, name='client_tracking'),
    ], 'operations'))),
    path('i18n/', include('django.conf.urls.i18n')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)