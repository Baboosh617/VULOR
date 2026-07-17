from django.db import models
from django.utils import timezone

import os
import uuid


def receipt_upload_path(instance, filename):
    """Store receipts under a date folder with an unguessable name —
    /media/ is publicly served, so the original filename must never be used."""
    ext = os.path.splitext(filename)[1].lower()
    return f"payment_receipts/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class PaymentTransactionQuerySet(models.QuerySet):
    def latest_for(self, order, statuses):
        """The order's most recent transaction in the given statuses, or None.
        The single owner of this lookup — don't hand-roll it in views."""
        return (
            self.filter(order=order, status__in=statuses)
            .order_by('-created_at')
            .first()
        )


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_verification', 'Pending Verification'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    ]

    objects = PaymentTransactionQuerySet.as_manager()

    reference = models.CharField(max_length=100, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    receipt = models.FileField(upload_to=receipt_upload_path, blank=True, null=True)
    transaction_reference = models.CharField(max_length=100, blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference} - {self.order.order_number}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=models.Q(status__in=['pending', 'pending_verification']),
                name='one_active_payment_per_order'
            )]
        ordering = ['-created_at']
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        indexes = [
            # status is filtered on every latest_for() call — the single
            # most frequently used payments lookup in the app.
            models.Index(fields=['status']),
        ]

    @staticmethod
    def generate_reference():

        return f"{uuid.uuid4().hex[:12]}-{int(timezone.now().timestamp())}"
