from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from cart.models import Cart
from services.email_service import send_abandoned_cart_email

class Command(BaseCommand):
    help = 'Send abandoned cart reminder emails'

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(hours=24)  # 24 hours inactive
        carts = Cart.objects.filter(
            is_ordered=False,
            abandoned_email_sent=False,
            updated_at__lte=cutoff
        )
        for cart in carts:
            send_abandoned_cart_email(cart.user, cart)
            cart.abandoned_email_sent = True
            cart.save(update_fields=['abandoned_email_sent'])
            self.stdout.write(f"Sent abandoned cart email to {cart.user.email}")

        self.stdout.write(self.style.SUCCESS('Abandoned cart emails sent successfully'))