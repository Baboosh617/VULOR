from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/<int:order_id>/', views.initiate_payment, name='initiate_payment'),
    path('verify/', views.verify_payment, name='verify_payment'),
    path('webhook/', views.webhook_view, name='webhook'),
    path('status/<str:reference>/', views.payment_status, name='payment_status'),
    path('success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('api/details/<int:order_id>/', views.get_payment_details, name='get_payment_details'),
]