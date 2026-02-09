from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from products import views as product_views
from accounts.views import register  
from services.admin_report_service import send_weekly_sales_report
from django.http import HttpResponse

import os

urlpatterns = [
    path(os.getenv('ADMIN_URL', 'admin/'), admin.site.urls),
   
    path('login/', auth_views.LoginView.as_view(template_name='account/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    # path('django_recaptcha/', include('django_recaptcha.urls')),
    
    
    
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('', product_views.home, name='home'),
    path('products/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('error-pages/', include('error_pages.urls')),
    path('services/', include('services.urls')),  
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)