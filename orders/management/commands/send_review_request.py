from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from orders.models import Order
from services.email_service import send_review_request

class Command(BaseCommand):
    help = 'Send review request emails to users'

    def handle(self, *args, **kwargs):
        three_days_ago = timezone.now() - timedelta(days=3)
        delivered_orders = Order.objects.filter(
            status='delivered',
            delivered_at__lte=three_days_ago,
            review_email_sent=False
        )
        for order in delivered_orders:
            send_review_request(order.user, order)
            order.review_email_sent = True
            order.save(update_fields=['review_email_sent'])
            self.stdout.write(f"Sent review request for order {order.id}")
