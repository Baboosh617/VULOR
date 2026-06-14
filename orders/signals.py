import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from services.email_service import (
    send_order_confirmation,
    send_admin_new_order,
    send_admin_high_value_order,
    send_admin_order_cancellation,
    send_payment_receipt,
    send_order_status_update,
)
from services.inventory_service import reduce_inventory, restock_order_items

logger = logging.getLogger(__name__)

HIGH_VALUE_THRESHOLD = 100000


# ─── Order Created ────────────────────────────────────────────────────────────
@receiver(post_save, sender=Order)
def handle_order_created(sender, instance, created, **kwargs):
    """
    Fires once when a brand new order is saved.
    Sends confirmation to customer + notifies admin.
    Guarded by admin_notified_new so it never fires twice.
    """
    if not created:
        return

    # Customer confirmation
    send_order_confirmation(instance.user, instance)

    # Admin new-order notification (guarded by flag)
    if not instance.admin_notified_new:
        send_admin_new_order(instance)
        Order.objects.filter(pk=instance.pk).update(admin_notified_new=True)


# ─── Payment Success ──────────────────────────────────────────────────────────
@receiver(post_save, sender=Order)
def handle_payment_success(sender, instance, **kwargs):
    """
    Fires when payment_status flips to 'success'.
    Reduces inventory, sends receipt.
    Both actions are guarded by their own flags so they never run twice.
    """
    if instance.payment_status != 'success':
        return

    # Reduce inventory once
    if not instance.inventory_adjusted:
        reduce_inventory(instance)
        Order.objects.filter(pk=instance.pk).update(inventory_adjusted=True)

    # Send payment receipt once
    if not instance.payment_email_sent:
        send_payment_receipt(instance.user, instance)
        Order.objects.filter(pk=instance.pk).update(payment_email_sent=True)


# ─── Shipped ──────────────────────────────────────────────────────────────────
@receiver(post_save, sender=Order)
def handle_order_shipped(sender, instance, **kwargs):
    """
    Fires when status flips to 'shipped'.
    Sends shipping update email once.
    """
    if instance.status != 'shipped':
        return

    if not instance.shipping_email_sent:
        send_order_status_update(instance.user, instance)
        Order.objects.filter(pk=instance.pk).update(shipping_email_sent=True)


# ─── High Value ───────────────────────────────────────────────────────────────
@receiver(post_save, sender=Order)
def handle_high_value_order(sender, instance, **kwargs):
    """
    Fires when a paid order exceeds the high-value threshold.
    Notifies admin once.
    """
    if instance.total_amount < HIGH_VALUE_THRESHOLD:
        return

    if instance.payment_status != 'success':
        return

    if not instance.admin_notified_high_value:
        send_admin_high_value_order(instance)
        Order.objects.filter(pk=instance.pk).update(admin_notified_high_value=True)


# ─── Cancellation ─────────────────────────────────────────────────────────────
@receiver(post_save, sender=Order)
def handle_order_cancellation(sender, instance, **kwargs):
    """
    Fires when status flips to 'cancelled'.
    Restocks inventory and notifies admin once each.
    """
    if instance.status != 'cancelled':
        return

    # Restock inventory
    restock_order_items(instance)

    # Notify admin once
    if not instance.admin_notified_cancellation:
        send_admin_order_cancellation(instance)
        Order.objects.filter(pk=instance.pk).update(admin_notified_cancellation=True)


# ─── Failed Payment ───────────────────────────────────────────────────────────
@receiver(post_save, sender=Order)
def handle_failed_payment(sender, instance, **kwargs):
    """
    Fires when payment_status flips to 'failed'.
    Restores inventory if it had previously been reduced.
    """
    if instance.payment_status != 'failed':
        return

    if instance.inventory_adjusted:
        restock_order_items(instance)
        Order.objects.filter(pk=instance.pk).update(inventory_adjusted=False)