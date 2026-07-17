from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
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


def send_templated_email(subject, template, user_id, order_id, to_email, extra_context=None):
    """Render and send a customer email. Called directly for synchronous
    delivery or via send_html_email_task when a Celery worker is available."""
    from django.contrib.auth import get_user_model
    from orders.models import Order

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    order = Order.objects.get(pk=order_id)
    context = build_order_email_context(user, order)
    if extra_context:
        context.update(extra_context)
    send_html(subject, template, context, to_email)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_html_email_task(self, subject, template, user_id, order_id, to_email, extra_context=None):
    send_templated_email(subject, template, user_id, order_id, to_email, extra_context=extra_context)


@shared_task(bind=True)
def abandon_stale_orders_task(self, hours=48):
    """Beat-schedulable wrapper around the abandon_stale_orders command."""
    from django.core.management import call_command
    call_command("abandon_stale_orders", hours=hours)


@shared_task(bind=True)
def send_weekly_sales_report_task(self):
    """Beat-schedulable wrapper around the report builder — the actual
    query/aggregation/email logic lives once in
    services.admin_report_service.send_weekly_sales_report, matching the
    abandon_stale_orders_task pattern above. Previously this task
    reimplemented that logic verbatim, so the two copies could drift."""
    from services.admin_report_service import send_weekly_sales_report
    send_weekly_sales_report()

