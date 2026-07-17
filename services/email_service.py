import logging
import mimetypes
import os
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from .tasks import send_html, send_html_email_task, send_templated_email

logger = logging.getLogger(__name__)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")


def _dispatch(subject, template, user, order, **extra_context):
    """Deliver a templated customer email. Queues via Celery only when
    EMAIL_ASYNC_ENABLED is set (worker + broker present); otherwise — or if
    the broker is unreachable — sends synchronously so emails are never
    silently dropped. `extra_context` (JSON-serialisable) is merged onto the
    shared order-email context for templates that need one-off values."""
    kwargs = dict(
        subject=subject,
        template=template,
        user_id=user.id,
        order_id=order.id,
        to_email=user.email,
        extra_context=extra_context or None,
    )
    if getattr(settings, "EMAIL_ASYNC_ENABLED", False):
        try:
            send_html_email_task.delay(**kwargs)
            return
        except Exception:
            logger.warning(
                f"Celery broker unavailable — sending '{subject}' synchronously",
                exc_info=True,
            )
    send_templated_email(**kwargs)


# ─── Internal helper ──────────────────────────────────────────────────────────
def send_html_email(subject, template, context, to_email):
    """Synchronous HTML email with caller-supplied context — used for sends
    that aren't tied to an order, like abandoned cart."""
    try:
        send_html(subject, template, context, to_email)
    except Exception:
        logger.error(f"Failed to send email: {subject}", exc_info=True)


# ─── Customer emails (async via Celery) ──────────────────────────────────────
def send_order_confirmation(user, order):
    _dispatch(
        subject=f"Your VULOR Order #{order.order_number} is Confirmed",
        template="emails/order_confirmation.html",
        user=user,
        order=order,
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

    _dispatch(
        subject=subject,
        template=template,
        user=user,
        order=order,
    )


def send_order_shipped(user, order):
    _dispatch(
        subject=f"VULOR Order #{order.order_number} Shipped!",
        template="emails/shipping_update.html",
        user=user,
        order=order,
    )


def send_order_out_for_delivery(user, order):
    _dispatch(
        subject=f"Order #{order.order_number} is Out for Delivery",
        template="emails/shipping_update.html",
        user=user,
        order=order,
    )


def send_order_delivered(user, order):
    _dispatch(
        subject=f"Order #{order.order_number} Delivered Successfully",
        template="emails/order_confirmation.html",
        user=user,
        order=order,
    )


def send_order_cancelled(user, order):
    _dispatch(
        subject=f"VULOR Order #{order.order_number} Cancelled",
        template="emails/order_confirmation.html",
        user=user,
        order=order,
    )


def send_payment_receipt(user, order):
    _dispatch(
        subject=f"Payment Receipt – Order #{order.order_number}",
        template="emails/payment_receipt.html",
        user=user,
        order=order,
    )


def send_payment_rejected(user, order, reason=None):
    _dispatch(
        subject=f"Payment Not Confirmed – Order #{order.order_number}",
        template="emails/payment_rejected.html",
        user=user,
        order=order,
        rejection_reason=(reason or "").strip(),
    )


def send_review_request(user, order):
    _dispatch(
        subject=f"Review Your Purchase – Order #{order.order_number}",
        template="emails/review_request.html",
        user=user,
        order=order,
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


def send_admin_contact_message(full_name, email, subject, message):
    if not ADMIN_EMAIL:
        logger.warning("ADMIN_EMAIL not set — skipping contact form notification")
        return
    # EmailMessage (not send_mail) so we can set reply_to — a staff member
    # replying to this notification should land in the customer's inbox.
    EmailMessage(
        subject=f"[Contact] {subject} — {full_name}",
        body=(
            f"From: {full_name} <{email}>\n"
            f"Subject: {subject}\n\n"
            f"{message}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[ADMIN_EMAIL],
        reply_to=[email],
    ).send()


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


def send_admin_payment_verification(order, txn):
    """Notify the store owner that a customer uploaded a transfer receipt.
    Synchronous with the receipt attached — this is the verification trigger
    and must not depend on the Celery broker being up."""
    if not ADMIN_EMAIL:
        logger.warning("ADMIN_EMAIL not set — skipping payment verification email")
        return

    items_lines = "\n".join(
        f"  - {item.quantity} x {item.product.name}"
        f"{f' (size: {item.size})' if item.size else ''}"
        f"{f' (color: {item.color})' if item.color else ''}"
        f" — ₦{item.get_total_price()}"
        for item in order.items.all()
    )

    body = (
        f"A payment receipt was uploaded for order {order.order_number}.\n\n"
        f"Customer: {order.shipping_full_name or order.user.username}\n"
        f"Email: {order.customer_email}\n"
        f"Phone: {order.customer_phone}\n"
        f"Address: {order.shipping_address}, {order.shipping_city}, {order.shipping_state}\n"
        f"Notes: {order.order_notes or '—'}\n\n"
        f"Items:\n{items_lines}\n\n"
        f"Subtotal: ₦{order.total_amount}\n"
        f"Shipping: ₦{order.shipping_fee}\n"
        f"Total due: ₦{order.grand_total}\n\n"
        f"Customer transaction reference: {txn.transaction_reference or '—'}\n\n"
        f"Verify the attached receipt, then confirm or reject the payment "
        f"in the dashboard."
    )

    msg = EmailMessage(
        subject=f"Verify payment – Order #{order.order_number}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[ADMIN_EMAIL],
    )
    if txn.receipt:
        with txn.receipt.open("rb") as f:
            content = f.read()
        mimetype = mimetypes.guess_type(txn.receipt.name)[0] or "application/octet-stream"
        msg.attach(os.path.basename(txn.receipt.name), content, mimetype)
    msg.send()


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