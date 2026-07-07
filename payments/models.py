from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

import uuid

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    channel = models.CharField(max_length=50, blank=True, null=True) 
    gateway_response = models.TextField(blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    verified_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Payment {self.reference} - {self.user.username} - ₦{self.amount}"

    @property
    def amount_in_kobo(self):
        return int(self.amount * 100)
    
class PaymentTransaction(models.Model):
    paystack_reference = models.CharField(max_length=100, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    paystack_access_code = models.CharField(max_length=200, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.paystack_reference} - {self.order.order_number}"    
    class Meta:
            constraints = [
                models.UniqueConstraint(
                fields=['order'],
                condition=models.Q(status__in=['pending', 'initiated']),
                name='one_active_payment_per_order'
            )]
            ordering = ['-created_at']
            verbose_name = 'Payment Transaction'
            verbose_name_plural = 'Payment Transactions'

    @property
    def amount_in_kobo(self):
        return int(self.amount * 100)

    @staticmethod
    def generate_reference():
        
        return f"{uuid.uuid4().hex[:12]}-{int(timezone.now().timestamp())}"