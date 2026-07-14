from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('transfer/<int:order_id>/', views.transfer_instructions, name='transfer_instructions'),
    path('transfer/<int:order_id>/submit/', views.submit_receipt, name='submit_receipt'),
    path('receipts/<int:txn_id>/', views.receipt_download, name='receipt_download'),
    path('success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('failed/<int:order_id>/', views.payment_failed, name='payment_failed'),
]
