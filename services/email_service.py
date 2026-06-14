import logging
import os
from django.core.mail import EmailMultiAlternatives, send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .tasks import send_html_email_task

logger = logging.getLogger(__name__)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")


# ─── Internal helper ──────────────────────────────────────────────────────────
def send_html_email(subject, template, context, to_email):
    """Synchronous HTML email — used for time-sensitive sends like abandoned cart."""
    try:
        html_content = render_to_string(template, context)
        text_content = render_to_string(template, context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception:
        logger.error(f"Failed to send email: {subject}", exc_info=True)


# ─── Customer emails (async via Celery) ──────────────────────────────────────
def send_order_confirmation(user, order):
    send_html_email_task.delay(
        subject=f"Your VULOR Order #{order.order_number} is Confirmed",
        template="emails/order_confirmation.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_status_update(user, order):
    """Sends shipping/status update email to customer."""
    status_subjects = {
        'shipped':   f"Your VULOR Order #{order.order_number} Has Shipped 🚚",
        'delivered': f"Your VULOR Order #{order.order_number} Has Been Delivered 📦",
        'cancelled': f"Your VULOR Order #{order.order_number} Has Been Cancelled",
    }
    subject = status_subjects.get(
        order.status,
        f"Update on Your VULOR Order #{order.order_number}"
    )

    template_map = {
        'shipped':   "emails/shipping_update.html",
        'delivered': "emails/order_confirmation.html",
        'cancelled': "emails/order_confirmation.html",
    }
    template = template_map.get(order.status, "emails/order_confirmation.html")

    send_html_email_task.delay(
        subject=subject,
        template=template,
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_shipped(user, order):
    send_html_email_task.delay(
        subject=f"VULOR Order #{order.order_number} Shipped!",
        template="emails/shipping_update.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_out_for_delivery(user, order):
    send_html_email_task.delay(
        subject=f"Order #{order.order_number} is Out for Delivery",
        template="emails/shipping_update.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_delivered(user, order):
    send_html_email_task.delay(
        subject=f"Order #{order.order_number} Delivered Successfully",
        template="emails/order_confirmation.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_cancelled(user, order):
    send_html_email_task.delay(
        subject=f"VULOR Order #{order.order_number} Cancelled",
        template="emails/order_confirmation.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_payment_receipt(user, order):
    send_html_email_task.delay(
        subject=f"Payment Receipt – Order #{order.order_number}",
        template="emails/payment_receipt.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_review_request(user, order):
    send_html_email_task.delay(
        subject=f"Review Your Purchase – Order #{order.order_number}",
        template="emails/review_request.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_abandoned_cart_email(user, cart):
    """Synchronous — abandoned cart emails are time-sensitive."""
    send_html_email(
        subject="You left something in your cart!",
        template="emails/abandoned_cart.html",
        context={"user": user, "cart": cart},
        to_email=user.email,
    )


# ─── Admin emails (plain send_mail — no template needed) ─────────────────────
def send_low_stock_alert(product):
    if not ADMIN_EMAIL:
        logger.warning("ADMIN_EMAIL not set — skipping low stock alert")
        return
    send_mail(
        subject=f"Low Stock Alert – {product.name}",
        message=(
            f"{product.name} is running low.\n"
            f"Current stock: {product.inventory_count}\n"
            f"Threshold: {product.low_stock_email_sent}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )


def send_admin_new_order(order):
    if not ADMIN_EMAIL:
        return
    send_mail(
        subject=f"New Order #{order.order_number}",
        message=(
            f"New order received.\n"
            f"Order: {order.order_number}\n"
            f"Customer: {order.user.email}\n"
            f"Total: ₦{order.total_amount}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )


def send_admin_high_value_order(order):
    if not ADMIN_EMAIL:
        return
    send_mail(
        subject=f"High-Value Order Alert – #{order.order_number}",
        message=(
            f"High-value order received!\n"
            f"Order: {order.order_number}\n"
            f"Customer: {order.user.email}\n"
            f"Total: ₦{order.total_amount}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )


def send_admin_order_cancellation(order):
    if not ADMIN_EMAIL:
        return
    send_mail(
        subject=f"Order #{order.order_number} Cancelled",
        message=(
            f"Order {order.order_number} was cancelled.\n"
            f"Customer: {order.user.email}\n"
            f"Total: ₦{order.total_amount}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )