from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from services.email_service import (
    send_order_confirmation,
    send_admin_new_order,
    send_admin_high_value_order,
    send_admin_order_cancellation,
    send_payment_receipt,
    send_order_shipped,
)
from services.inventory_service import reduce_inventory, restock_order_items
import logging

logger = logging.getLogger(__name__)
HIGH_VALUE_THRESHOLD = 100000


@receiver(post_save, sender=Order)
def order_created(sender, instance, created, **kwargs):
    if created and not instance.admin_notified_new:
        send_order_confirmation(instance.user, instance)
        send_admin_new_order(instance)
        instance.admin_notified_new = True
        instance.save(update_fields=["admin_notified_new"])


@receiver(post_save, sender=Order)
def payment_success(sender, instance, created, **kwargs):
    if created:
        return
    if instance.payment_status == "success" and not instance.inventory_adjusted:
        reduce_inventory(instance)
        instance.inventory_adjusted = True
        instance.save(update_fields=["inventory_adjusted"])
    if instance.payment_status == "success" and not instance.payment_email_sent:
        send_payment_receipt(instance.user, instance)
        instance.payment_email_sent = True
        instance.save(update_fields=["payment_email_sent"])


@receiver(post_save, sender=Order)
def high_value_order(sender, instance, created, **kwargs):
    if created:
        return
    if instance.total_amount >= HIGH_VALUE_THRESHOLD and not instance.admin_notified_high_value:
        send_admin_high_value_order(instance)
        instance.admin_notified_high_value = True
        instance.save(update_fields=["admin_notified_high_value"])


@receiver(post_save, sender=Order)
def shipping_update(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status == "shipped" and not instance.shipping_email_sent:
        send_order_shipped(instance.user, instance)
        instance.shipping_email_sent = True
        instance.save(update_fields=["shipping_email_sent"])


@receiver(post_save, sender=Order)
def cancellation_and_failure(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status == "cancelled" and not instance.admin_notified_cancellation:
        if instance.inventory_adjusted:
            restock_order_items(instance)
            instance.inventory_adjusted = False
        send_admin_order_cancellation(instance)
        instance.admin_notified_cancellation = True
        instance.save(update_fields=["admin_notified_cancellation", "inventory_adjusted"])
    if instance.payment_status == "failed" and instance.inventory_adjusted:
        restock_order_items(instance)
        instance.inventory_adjusted = False
        instance.save(update_fields=["inventory_adjusted"])