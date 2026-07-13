from django.db import models
from django.utils import timezone

import os
import uuid


def receipt_upload_path(instance, filename):
    """Store receipts under a date folder with an unguessable name —
    /media/ is publicly served, so the original filename must never be used."""
    ext = os.path.splitext(filename)[1].lower()
    return f"payment_receipts/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),  # legacy Paystack rows
        ('pending_verification', 'Pending Verification'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    ]

    # Legacy Paystack columns — still used by payments/views.py until the
    # bank-transfer view rewrite lands; renamed/dropped in that same change.
    paystack_reference = models.CharField(max_length=100, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    paystack_access_code = models.CharField(max_length=200, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    receipt = models.FileField(upload_to=receipt_upload_path, blank=True, null=True)
    transaction_reference = models.CharField(max_length=100, blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.paystack_reference} - {self.order.order_number}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=models.Q(status__in=['pending', 'initiated', 'pending_verification']),
                name='one_active_payment_per_order'
            )]
        ordering = ['-created_at']
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'

    @property
    def amount_in_kobo(self):
        # Legacy — payments/views.py still cross-checks Paystack amounts in
        # kobo; goes away with the bank-transfer view rewrite.
        return int(self.amount * 100)

    @staticmethod
    def generate_reference():

        return f"{uuid.uuid4().hex[:12]}-{int(timezone.now().timestamp())}"
