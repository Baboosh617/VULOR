from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path('profile/', views.profile_view, name='profile_view'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('size-guide/', views.size_guide, name='size_guide'),
]