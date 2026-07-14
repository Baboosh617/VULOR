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

     
            
    # def handle_status_change(self, old_status):
    #     """Handle inventory changes when order status changes"""
    #     if old_status != self.status and self.payment_status == 'success':
    #         self.reduce_inventory()
    #         if not self.payment_email_sent:
    #             send_order_confirmation(self.user, self)
    #             self.payment_email_sent = True
    #             self.save(update_fields=['payment_email_sent'])
            
    #         if not self.admin_notified_new:
    #             send_admin_high_value_order(self)
    #             self.admin_notified_new = True
    #             self.save(update_fields=['admin_notified_new'])
    #     elif old_status != self.status and self.payment_status == 'cancelled':
    #         self.restore_inventory()
          

        
    #     elif old_status == 'success' and self.status == 'cancelled':
    #         self.restore_inventory()
        
       
    
    # def reduce_inventory(self):
    #     """Reduce inventory for all items in this order"""
    #     if self.inventory_adjusted:
    #         return

    #     with transaction.atomic():
    #         for item in self.items.all():
    #             product = Product.objects.select_for_update().get(id=item.product.id)
    #             quantity = item.quantity
                
    #             # Check if enough stock
    #             if product.inventory_count < quantity:
    #                 # If not enough, set order to pending and notify admin
    #                 self.status = 'pending'
    #                 self.save(update_fields=['status'])
    #                 raise ValueError(
    #                     f"Insufficient stock for {product.name}. "
    #                     f"Available: {product.inventory_count}, "
    #                     f"Requested: {quantity}"
    #                 )
                
    #             # Reduce inventory safely
    #             Product.objects.filter(id=product.id).update(
    #                 inventory_count=F('inventory_count') - quantity
    #             )
                
    #             # Refresh product instance
    #             product.refresh_from_db()
                
    #             # Check if low stock and send alert (optional)
    #             if product.inventory_count <= 5 and not product.low_stock_email_sent:
    #                 # You could add a low stock email here
    #                 product.low_stock_email_sent = True
    #                 product.save(update_fields=['low_stock_email_sent'])
    #     logger.info(f"Inventory adjusted for order {self.id}")
    #     self.inventory_adjusted = True
    #     self.save(update_fields=['inventory_adjusted'])                    
    
    # def restore_inventory(self):
    #     """Restore inventory when order is cancelled"""
    #     with transaction.atomic():
    #         for item in self.items.all():
    #             product = item.product
    #             quantity = item.quantity
                
    #             # Restore inventory
    #             Product.objects.filter(id=product.id).update(
    #                 inventory_count=F('inventory_count') + quantity
    #             )
                
    #             # Reset low stock flag if inventory is now above threshold
    #             product.refresh_from_db()
    #             if product.inventory_count > 5:
    #                 product.low_stock_email_sent = False
    #                 product.save(update_fields=['low_stock_email_sent'])

       

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
        the customer receipt email. Used by the dashboard and Django admin."""
        from django.utils import timezone
        from payments.models import PaymentTransaction

        txn = PaymentTransaction.objects.latest_for(
            self, ["pending", "pending_verification"]
        )
        if txn:
            txn.status = "success"
            txn.verified_at = timezone.now()
            txn.save(update_fields=["status", "verified_at"])

        self.payment_status = "success"
        self.save()

    def reject_payment(self):
        """Reject the receipt awaiting verification and email the customer to
        retry from the transfer page. Used by the dashboard and Django admin."""
        from payments.models import PaymentTransaction
        from services.email_service import send_payment_rejected

        txn = PaymentTransaction.objects.latest_for(self, ["pending_verification"])
        if txn:
            txn.status = "rejected"
            txn.save(update_fields=["status"])

        self.payment_status = "failed"
        self.save()

        try:
            send_payment_rejected(self.user, self)
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