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


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_html_email_task(self, subject, template, user_id, order_id, to_email):
    from django.contrib.auth import get_user_model
    from orders.models import Order

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    order = Order.objects.get(pk=order_id)
    context = {
        "user": user,
        "order": order,
        "site_url": settings.SITE_URL,
        "bank_name": settings.BANK_TRANSFER_BANK_NAME,
        "account_name": settings.BANK_TRANSFER_ACCOUNT_NAME,
        "account_number": settings.BANK_TRANSFER_ACCOUNT_NUMBER,
    }

    html_content = render_to_string(template, context)
    text_content = render_to_string(template, context).strip()

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


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

