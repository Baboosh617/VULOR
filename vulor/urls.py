import posixpath

from django.contrib import admin
from django.http import Http404
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.views.static import serve
from products import views as product_views
from accounts.views import register

import os


def serve_media_excluding_receipts(request, path, document_root=None, show_indexes=False):
    """Production media serving for everything except payment receipts.

    Payment receipts are confidential bank documents and must only ever be
    reachable through the staff-gated payments:receipt_download view — never
    directly under /media/. Normalize the requested path the same way
    django.views.static.serve does before comparing, so path traversal
    (`..`) or case tricks can't sneak a receipt through.
    """
    normalized = posixpath.normpath(path).lstrip("/").lower()
    if normalized.startswith("payment_receipts/") or ".." in normalized.split("/"):
        raise Http404("Not found")
    return serve(request, path, document_root=document_root, show_indexes=show_indexes)

urlpatterns = [
    path(os.getenv('ADMIN_URL', 'admin/'), admin.site.urls),

    path('login/', auth_views.LoginView.as_view(template_name='account/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('', product_views.home, name='home'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
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
else:
    # WhiteNoise only serves STATIC_ROOT, not MEDIA_ROOT, so without this
    # product images 404 in production. Payment receipts are excluded —
    # see serve_media_excluding_receipts above and payments:receipt_download.
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve_media_excluding_receipts,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

# Custom error handlers — Django only reads these as module-level names in
# the root URLconf, and only takes effect when DEBUG is False.
handler404 = "error_pages.views.custom_404"
handler500 = "error_pages.views.custom_500"
handler403 = "error_pages.views.custom_403"
handler400 = "error_pages.views.custom_400"