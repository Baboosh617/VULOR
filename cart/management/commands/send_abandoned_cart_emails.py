# cart/management/commands/send_abandoned_cart_emails.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from cart.models import Cart
from services.email_service import send_abandoned_cart_email
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send abandoned cart reminder emails to users who have items but have not checked out'

    def handle(self, *args, **kwargs):
        # A cart is "abandoned" if it hasn't been updated in 24 hours
        # and the user has NOT placed a paid order since the cart was last updated
        cutoff = timezone.now() - timedelta(hours=24)

        carts = Cart.objects.filter(
            updated_at__lte=cutoff
        ).prefetch_related('items', 'user')

        sent = 0
        skipped = 0

        for cart in carts:
            # Skip empty carts
            if not cart.items.exists():
                skipped += 1
                continue

            # Skip if user has a recent paid order (they checked out another way)
            from orders.models import Order
            recent_order = Order.objects.filter(
                user=cart.user,
                payment_status='success',
                created_at__gte=cart.updated_at
            ).exists()

            if recent_order:
                skipped += 1
                continue

            try:
                send_abandoned_cart_email(cart.user, cart)
                sent += 1
                self.stdout.write(f"Sent abandoned cart email to {cart.user.email}")
            except Exception as e:
                logger.error(f"Failed to send abandoned cart email to {cart.user.email}: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Sent: {sent}, Skipped: {skipped}'
            )
        )