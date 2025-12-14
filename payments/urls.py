from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/<int:order_id>/', views.initiate_payment, name='initiate_payment'),
    path('get-details/<int:order_id>/', views.get_payment_details, name='get_payment_details'),
    path('verify/', views.verify_payment, name='verify_payment'),
    path('webhook/paystack/', views.paystack_webhook, name='paystack_webhook'),
    path('success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('failed/<int:order_id>/', views.payment_failed, name='payment_failed'),
]
