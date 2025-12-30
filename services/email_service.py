from django.core.mail import EmailMultiAlternatives, send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging
import os

logger = logging.getLogger(__name__)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")


def send_html_email(subject, template, context, to_email):
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


# ===================== USER EMAILS =====================

def send_order_confirmation(user, order):
    send_html_email(
        subject=f"Your VULOR Order #{order.id} is Confirmed",
        template="emails/order_confirmation.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_shipped(user, order):
    send_html_email(
        subject=f"VULOR Order #{order.id} Shipped!",
        template="emails/shipping_update.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_out_for_delivery(user, order):
    send_html_email(
        subject=f"Order #{order.id} is Out for Delivery",
        template="emails/out_for_delivery.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_delivered(user, order):
    send_html_email(
        subject=f"Order #{order.id} Delivered Successfully",
        template="emails/order_delivered.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_order_cancelled(user, order):
    send_html_email(
        subject=f"VULOR Order #{order.id} Cancelled",
        template="emails/order_cancelled.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_payment_receipt(user, order):
    send_html_email(
        subject=f"Payment Receipt – Order #{order.id}",
        template="emails/payment_receipt.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_review_request(user, order):
    send_html_email(
        subject=f"Review Your Purchase – Order #{order.id}",
        template="emails/review_request.html",
        context={"user": user, "order": order},
        to_email=user.email,
    )


def send_abandoned_cart_email(user, cart):
    send_html_email(
        subject="You left something in your cart!",
        template="emails/abandoned_cart.html",
        context={"user": user, "cart": cart},
        to_email=user.email,
    )


# ===================== ADMIN EMAILS =====================

def send_low_stock_alert(product):
    send_mail(
        subject=f"Low Stock Alert – {product.name}",
        message=f"{product.name} stock is low. Current stock: {product.inventory_count}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )


def send_admin_new_order(order):
    send_mail(
        subject=f"New Order #{order.id} Placed",
        message=f"Order #{order.id} by {order.user.username} totaling ₦{order.get_total_price()}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )


def send_admin_high_value_order(order):
    send_mail(
        subject=f"High-Value Order Alert #{order.id}",
        message=f"Order #{order.id} totaling ₦{order.get_total_price()} requires attention.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )


def send_admin_order_cancellation(order):
    send_mail(
        subject=f"Order #{order.id} Cancelled",
        message=f"Order #{order.id} by {order.user.username} was cancelled.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
    )
