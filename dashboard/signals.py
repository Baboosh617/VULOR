# dashboard/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

@receiver(post_save, sender=Order)
def send_order_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "admin_notifications",
            {
                "type": "send_notification",
                "message": {
                    "text": f"New order received from {instance.user.username}!",
                    "order_id": instance.id
                }
            }
        )
