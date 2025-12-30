from django.db import models, transaction
from django.db.models import F
from django.contrib.auth import get_user_model
from products.models import Product
from services.email_service import (
    send_order_confirmation,
    send_order_shipped,
    send_order_out_for_delivery,    
    send_order_delivered,
    send_order_cancelled,
    send_admin_new_order,
    send_admin_high_value_order,
)
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
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    ]

    # --------- CORE FIELDS ----------
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="orders_made")
    order_number = models.CharField(max_length=20, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    inventory_adjusted = models.BooleanField(default=False)

    # ✅ Email tracking booleans
    payment_email_sent = models.BooleanField(default=False)
    shipping_email_sent = models.BooleanField(default=False)
    review_email_sent = models.BooleanField(default=False)

    admin_notified_new = models.BooleanField(default=False)
    admin_notified_high_value = models.BooleanField(default=False)
    admin_notified_cancellation = models.BooleanField(default=False)

    # Order & timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------- SHIPPING ----------
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_zipcode = models.CharField(max_length=20, default='00000')
    shipping_country = models.CharField(max_length=100, default='Nigeria')
    shipping_full_name = models.CharField(max_length=200, blank=True, default='')

    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    shipping_zone = models.CharField(max_length=50, blank=True, default='')

    # --------- CUSTOMER ----------
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True, default='')

    # --------- PAYSTACK ----------
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    paystack_reference = models.CharField(max_length=100, blank=True)
    paystack_access_code = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, default='paystack')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    # --------- UTILS ----------
    @property
    def paystack_amount(self):
        total_with_shipping = self.total_amount + self.shipping_fee
        return int(total_with_shipping * 100)
    
    @property
    def grand_total(self):
        """Calculate grand total including shipping"""
        return self.total_amount + self.shipping_fee

    # --------- SAVE OVERRIDE ----------
    def save(self, *args, **kwargs):
    # Get old status for comparison
     old_status = None
     if self.pk:
         try:
             old_status = Order.objects.get(pk=self.pk).status
         except Order.DoesNotExist:
             old_status = None
     
     # Auto-generate order number
     if not self.pk and not self.order_number:
         import time
         self.order_number = f"VU{self.user.id:06d}{int(time.time())}{uuid4().hex[:4]}"
     
     # Skip email logic for NEW orders to prevent the group_send error
     # Save without calling handle_status_change for new orders
     if not self.pk:
         # This is a new order - save without triggering email logic
         super().save(*args, **kwargs)
         return
     
     # For existing orders, proceed with the original logic
     with transaction.atomic():
         super().save(*args, **kwargs)
         
         if old_status != self.status:
             self.handle_status_change(old_status)
     
            
    def handle_status_change(self, old_status):
        """Handle inventory changes when order status changes"""
        if old_status != self.status and self.payment_status == 'success':
            self.reduce_inventory()
            if not self.payment_email_sent:
                send_order_confirmation(self.user, self)
                self.payment_email_sent = True
                self.save(update_fields=['payment_email_sent'])
            
            if not self.admin_notified_new:
                send_admin_high_value_order(self)
                self.admin_notified_new = True
                self.save(update_fields=['admin_notified_new'])
        elif old_status != self.status and self.payment_status == 'cancelled':
            self.restore_inventory()
          

        
        elif old_status == 'success' and self.status == 'cancelled':
            self.restore_inventory()
        
       
    
    def reduce_inventory(self):
        """Reduce inventory for all items in this order"""
        if self.inventory_adjusted:
            return

        with transaction.atomic():
            for item in self.items.all():
                product = Product.objects.select_for_update().get(id=item.product.id)
                quantity = item.quantity
                
                # Check if enough stock
                if product.inventory_count < quantity:
                    # If not enough, set order to pending and notify admin
                    self.status = 'pending'
                    self.save(update_fields=['status'])
                    raise ValueError(
                        f"Insufficient stock for {product.name}. "
                        f"Available: {product.inventory_count}, "
                        f"Requested: {quantity}"
                    )
                
                # Reduce inventory safely
                Product.objects.filter(id=product.id).update(
                    inventory_count=F('inventory_count') - quantity
                )
                
                # Refresh product instance
                product.refresh_from_db()
                
                # Check if low stock and send alert (optional)
                if product.inventory_count <= 5 and not product.low_stock_email_sent:
                    # You could add a low stock email here
                    product.low_stock_email_sent = True
                    product.save(update_fields=['low_stock_email_sent'])
        logger.info(f"Inventory adjusted for order {self.id}")
        self.inventory_adjusted = True
        self.save(update_fields=['inventory_adjusted'])                    
    
    def restore_inventory(self):
        """Restore inventory when order is cancelled"""
        with transaction.atomic():
            for item in self.items.all():
                product = item.product
                quantity = item.quantity
                
                # Restore inventory
                Product.objects.filter(id=product.id).update(
                    inventory_count=F('inventory_count') + quantity
                )
                
                # Reset low stock flag if inventory is now above threshold
                product.refresh_from_db()
                if product.inventory_count > 5:
                    product.low_stock_email_sent = False
                    product.save(update_fields=['low_stock_email_sent'])

       

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
        # If this is a new item and order is completed, check stock
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