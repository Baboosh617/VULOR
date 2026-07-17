from django.db import models, transaction
from django.db.models import F
from django.contrib.auth import get_user_model
from products.models import Product
from accounts.models import CustomUser
from uuid import uuid4
from django.core.validators import MinValueValidator
import logging

User = get_user_model()

logger = logging.getLogger(__name__)
class Order(models.Model):

    # --------- CHOICES ----------
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_verification', 'Pending Verification'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    ]

    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="orders_made")
    order_number = models.CharField(max_length=20, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    inventory_adjusted = models.BooleanField(default=False)

    
    payment_email_sent = models.BooleanField(default=False)
    shipping_email_sent = models.BooleanField(default=False)
    review_email_sent = models.BooleanField(default=False)

    admin_notified_new = models.BooleanField(default=False)
    admin_notified_high_value = models.BooleanField(default=False)
    admin_notified_cancellation = models.BooleanField(default=False)

    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_zipcode = models.CharField(max_length=20, default='00000')
    shipping_country = models.CharField(max_length=100, default='Nigeria')
    shipping_full_name = models.CharField(max_length=200, blank=True, default='')

    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    shipping_zone = models.CharField(max_length=50, blank=True, default='')

    
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True, default='')
    order_notes = models.TextField(blank=True, default='')

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, default='bank_transfer')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # payment_status/status/created_at are each filtered or ordered
            # on constantly (dashboard stats, order_list, abandon_stale_orders,
            # the default ordering itself) with no index today — invisible on
            # SQLite, a real cost on Postgres production as tables grow.
            models.Index(fields=['payment_status']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.order_number

    @property
    def grand_total(self):
        """Calculate grand total including shipping"""
        return self.total_amount + self.shipping_fee

    
    def save(self, *args, **kwargs):
        if not self.pk and not self.order_number:
            import time
            self.order_number = f"VU{self.user.id:06d}{int(time.time())}{uuid4().hex[:4]}"
        super().save(*args, **kwargs)

    # ---- Payment transitions — the only place payment_status changes ----

    def submit_receipt(self, txn):
        """Store the customer's uploaded receipt and move the order into
        verification. `txn` is the (unsaved) transaction carrying the upload."""
        from django.utils import timezone

        with transaction.atomic():
            txn.status = "pending_verification"
            txn.submitted_at = timezone.now()
            txn.save()

            self.payment_status = "pending_verification"
            self.save(update_fields=["payment_status", "updated_at"])

    def confirm_payment(self):
        """Mark the active transaction and this order as paid. The
        payment_success post_save signal then reduces inventory and sends
        the customer receipt email. Used by the dashboard and Django admin.

        Row-locked and re-checked inside the lock: two overlapping calls for
        the same order (a double-submitted confirm click, two staff acting
        on the same order) must not both pass and both trigger inventory
        reduction — only the caller that wins the lock while the order is
        still not 'success' performs the transition; a loser is a no-op."""
        from django.utils import timezone
        from payments.models import PaymentTransaction

        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=self.pk)
            if locked.payment_status != "success":
                txn = PaymentTransaction.objects.latest_for(
                    locked, ["pending", "pending_verification"]
                )
                if txn:
                    txn.status = "success"
                    txn.verified_at = timezone.now()
                    txn.save(update_fields=["status", "verified_at"])

                locked.payment_status = "success"
                locked.save()

        self.refresh_from_db()

    def reject_payment(self, reason=None):
        """Reject the receipt awaiting verification and email the customer to
        retry from the transfer page. Used by the dashboard and Django admin.
        `reason` (optional) is a staff note included in the rejection email.

        Row-locked the same way as confirm_payment, so two overlapping
        rejects for the same order don't both mutate state or both send the
        customer a rejection email."""
        from payments.models import PaymentTransaction
        from services.email_service import send_payment_rejected

        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=self.pk)
            already_rejected = locked.payment_status != "pending_verification"
            if not already_rejected:
                txn = PaymentTransaction.objects.latest_for(locked, ["pending_verification"])
                if txn:
                    txn.status = "rejected"
                    txn.save(update_fields=["status"])

                locked.payment_status = "failed"
                locked.save()

        self.refresh_from_db()

        if already_rejected:
            return

        try:
            send_payment_rejected(self.user, self, reason=reason)
        except Exception:
            logger.error(
                f"Failed to send payment rejection email for order {self.id}",
                exc_info=True,
            )

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    @property
    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())
    
    def is_paid(self):
        return self.payment_status == 'success'
    
    @property
    def total(self):
        """Alias for total_amount for backward compatibility"""
        return self.total_amount

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=10, blank=True)
    color = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        """Validate stock when creating order items"""
        
        if not self.pk and self.order.status == 'completed':
            if self.product.inventory_count < self.quantity:
                raise ValueError(
                    f"Cannot add {self.quantity} of {self.product.name}. "
                    f"Only {self.product.inventory_count} available."
                )
        super().save(*args, **kwargs)
    
    def get_total_price(self):
        return self.quantity * self.price

    class Meta:
        ordering = ['-order__created_at']