from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils.timezone import now, timedelta
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from products.models import Product
import logging

logger = logging.getLogger(__name__)


def send_html(subject, template, context, to_email):
    """Render and send one HTML email; the text alternative is derived from
    the same render. The single email builder for the whole project."""
    html_content = render_to_string(template, context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(html_content).strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def build_order_email_context(user, order):
    """Context for every order-related customer email: bank details shared
    with the transfer page, and absolute links built via reverse() so they
    can't rot when routes move."""
    from django.urls import reverse
    from payments.utils import get_bank_details

    return {
        "user": user,
        "order": order,
        "site_url": settings.SITE_URL,
        "order_url": settings.SITE_URL + reverse("orders:order_detail", args=[order.order_number]),
        "payment_url": settings.SITE_URL + reverse("payments:transfer_instructions", args=[order.id]),
        **get_bank_details(),
    }


def send_templated_email(subject, template, user_id, order_id, to_email):
    """Render and send a customer email. Called directly for synchronous
    delivery or via send_html_email_task when a Celery worker is available."""
    from django.contrib.auth import get_user_model
    from orders.models import Order

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    order = Order.objects.get(pk=order_id)
    send_html(subject, template, build_order_email_context(user, order), to_email)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_html_email_task(self, subject, template, user_id, order_id, to_email):
    send_templated_email(subject, template, user_id, order_id, to_email)


@shared_task(bind=True)
def abandon_stale_orders_task(self, hours=48):
    """Beat-schedulable wrapper around the abandon_stale_orders command."""
    from django.core.management import call_command
    call_command("abandon_stale_orders", hours=hours)


@shared_task(bind=True)
def send_weekly_sales_report_task(self):
    from orders.models import OrderItem, Order
    start_date = now() - timedelta(days=7)

    order_items = OrderItem.objects.filter(order__created_at__gte=start_date)
    orders = Order.objects.filter(created_at__gte=start_date)

    total_revenue = (
        order_items.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("price"),
                    output_field=DecimalField()
                )
            )
        )["total"] or 0
    )

    total_orders = orders.count()
    low_stock_products = Product.objects.filter(inventory_count__lte=5)

    product_sales = (
        order_items
        .values(product_name=F("product__name"))
        .annotate(
            total_quantity=Sum("quantity"),
            total_revenue=Sum(
                ExpressionWrapper(
                    F("quantity") * F("price"),
                    output_field=DecimalField()
                )
            )
        )
        .order_by("-total_quantity")
    )

    context = {
        "order_items": order_items,
        "orders": orders,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "low_stock_products": low_stock_products,
        "product_sales": product_sales,
    }

    html_body = render_to_string("emails/weekly_sales_report.html", context)
    text_body = strip_tags(html_body)

    msg = EmailMultiAlternatives(
        subject="VULOR — Weekly Sales Report",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.ADMIN_EMAIL],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()

