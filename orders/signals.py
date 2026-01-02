from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from services.email_service import (
    send_order_confirmation,
    send_admin_new_order,
    send_admin_high_value_order,
    send_admin_order_cancellation,
    send_payment_receipt
)
from services.inventory_service import reduce_inventory, restock_order_items

HIGH_VALUE_THRESHOLD = 100000  # example threshold

@receiver(post_save, sender=Order)
def order_created(sender, instance, created, **kwargs):
    if created:
        send_order_confirmation(instance.user, instance)
        send_admin_new_order(instance)

@receiver(post_save, sender=Order)
def payment_success(sender, instance, **kwargs):
    if instance.payment_status == "success" and not instance.inventory_adjusted:
        reduce_inventory(instance)
        send_payment_receipt(instance.user, instance)
        instance.inventory_adjusted = True
        instance.save(update_fields=["inventory_adjusted"])

@receiver(post_save, sender=Order)
def high_value_order(sender, instance, **kwargs):
    if instance.get_total_price >= HIGH_VALUE_THRESHOLD and not instance.admin_notified_high_value:
        send_admin_high_value_order(instance)
        instance.admin_notified_high_value = True
        instance.save(update_fields=["admin_notified_high_value"])

@receiver(post_save, sender=Order)
def cancellation(sender, instance, **kwargs):
    if instance.status == "cancelled":
        restock_order_items(instance)



@receiver(post_save, sender=Order)
def send_payment_receipt_signal(sender, instance, **kwargs):
    if instance.is_paid and not instance.payment_email_sent:
        from services.email_service import send_payment_receipt
        send_payment_receipt(instance.user, instance)
        instance.payment_email_sent = True
        instance.save(update_fields=['payment_email_sent'])

@receiver(post_save, sender=Order)
def send_shipping_update_signal(sender, instance, **kwargs):
    if instance.status == 'shipped' and not instance.shipping_email_sent:
        from services.email_service import send_order_status_update
        send_order_status_update(instance.user, instance)
        instance.shipping_email_sent = True
        instance.save(update_fields=['shipping_email_sent'])

@receiver(post_save, sender=Order)
def admin_notifications(sender, instance, created, **kwargs):
    # New order
    if created and not instance.admin_notified_new:
        send_admin_new_order(instance)
        instance.admin_notified_new = True
        instance.save(update_fields=['admin_notified_new'])

    # High-value order
    if instance.total >= HIGH_VALUE_THRESHOLD and not instance.admin_notified_high_value:
        send_admin_high_value_order(instance)
        instance.admin_notified_high_value = True
        instance.save(update_fields=['admin_notified_high_value'])

    # Cancellation (assumes you mark a status field as 'cancelled')
    if instance.status == 'cancelled' and not instance.admin_notified_cancellation:
        send_admin_order_cancellation(instance)
        instance.admin_notified_cancellation = True
        instance.save(update_fields=['admin_notified_cancellation'])

@receiver(post_save, sender=Order)
def auto_inventory_sync(sender, instance, created, **kwargs):
    """
    Sync inventory when an order is cancelled or fails payment.
    """
    # When order is first created → stock already deducted in checkout logic
    if created:
        return

    # Handle cancellation
    if instance.status == "cancelled" and not instance.admin_notified_cancellation:
        restock_order_items(instance)

    # Handle failed payment / expired
    if instance.status == "failed":
        restock_order_items(instance)


import logging
logger = logging.getLogger(__name__)

def restock_order_items(order):
    for item in order.items.all():
        product = item.product
        product.stock += item.quantity
        product.save(update_fields=["stock"])

        logger.info(f"Restocked {item.quantity} of {product.name} from order {order.id}.")
