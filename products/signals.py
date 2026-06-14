# products/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def low_stock_signal(sender, instance, **kwargs):
    """
    Alert admin when a product's inventory drops to or below 5.
    Uses inventory_count (not stock) and guards with low_stock_email_sent.
    """
    threshold = 5

    if instance.inventory_count > threshold:
        # If stock has recovered, reset the flag so future alerts can fire
        if instance.low_stock_email_sent:
            Product.objects.filter(pk=instance.pk).update(low_stock_email_sent=False)
        return

    if instance.inventory_count <= threshold and not instance.low_stock_email_sent:
        try:
            from services.email_service import send_low_stock_alert
            send_low_stock_alert(instance)
            Product.objects.filter(pk=instance.pk).update(low_stock_email_sent=True)
            logger.info(f"Low stock alert sent for {instance.name} (stock: {instance.inventory_count})")
        except Exception:
            logger.error(f"Failed to send low stock alert for {instance.name}", exc_info=True)