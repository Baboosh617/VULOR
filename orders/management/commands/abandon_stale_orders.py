import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order
from payments.models import PaymentTransaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Mark unpaid orders older than --hours (default 48) as abandoned so "
        "they stop blocking new checkouts. Orders with a receipt awaiting "
        "verification are left alone."
    )

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=48)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(hours=options["hours"])
        stale = Order.objects.filter(
            payment_status="pending", created_at__lt=cutoff
        )

        count = 0
        for order in stale:
            PaymentTransaction.objects.filter(
                order=order, status__in=["pending", "initiated"]
            ).update(status="failed")
            order.payment_status = "abandoned"
            order.save(update_fields=["payment_status", "updated_at"])
            logger.info(f"Order {order.order_number} abandoned after {options['hours']}h unpaid")
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Abandoned {count} stale order(s)."))
