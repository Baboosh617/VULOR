from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    # Shadows allauth's signup view (this include sits above allauth's in the
    # root URLconf) so there is exactly one signup door.
    path("signup/", RedirectView.as_view(pattern_name="register", query_string=True)),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/deactivate/', views.deactivate_account, name='deactivate_account'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('size-guide/', views.size_guide, name='size_guide'),
]