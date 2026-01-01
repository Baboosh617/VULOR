from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product
from services.email_service import send_low_stock_alert

@receiver(post_save, sender=Product)
def low_stock_signal(sender, instance, **kwargs):
    threshold = 5  
    if instance.stock <= threshold and not instance.low_stock_email_sent:
        send_low_stock_alert(instance)
        instance.low_stock_email_sent = True
        instance.save(update_fields=['low_stock_email_sent'])
