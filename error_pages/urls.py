from django.urls import path
from . import views
from django.conf import settings
from django.shortcuts import render
urlpatterns = [
    # No public URLs for error pages; they are handled globally
]

# For testing error pages in development
if settings.DEBUG:
    urlpatterns += [
        path('404/', lambda request: render(request, '404.html')),
        path('500/', lambda request: render(request, '500.html')),
        path('403/', lambda request: render(request, '403.html')),
        path('400/', lambda request: render(request, '400.html')),
    ]