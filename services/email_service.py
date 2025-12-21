from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.contrib.auth.models import User

ADMIN_EMAIL = "babasmuhammad617@gmail.com"

user = User()

def send_order_confirmation(user, order):
    try:
        subject = f"Your VULOR Order #{order.id} is Confirmed"
        message = (
            f"Hey {user.first_name},\n\n"
            f"Your order has been successfully placed!\n"
            f"Order ID: {order.id}\n"
            f"Total: ₦{order.get_total_price}\n\n"
            f"We’ll keep you updated.\n"
            f"— VULOR Team"
        )
        
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as e:
        # Log the exception (you can use logging framework here)
        print(f"Failed to send order confirmation email: {e}")    

def send_order_shipped(user, order):
    subject = f"VULOR Order #{order.id} Shipped!"
    message = (
        f"Good news, {user.first_name}!\n\n"
        f"Your order is now on the way.\n"
        f"Order ID: {order.id}\n\n"
        f"You’ll receive another update when it's out for delivery.\n"
        f"— VULOR Team"
    )
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

def send_order_out_for_delivery(user, order):
    subject = f"Order #{order.id} is Out for Delivery"
    message = (
        f"{user.first_name}, your VULOR order is almost there!\n\n"
        f"Order ID: {order.id}\n"
        f"Our rider is bringing it to your location right now.\n"
        f"— VULOR Team"
    )
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_order_delivered(user, order):
    subject = f"Order #{order.id} Delivered Successfully"
    message = (
        f"We delivered it! 🎉\n\n"
        f"Order ID: {order.id}\n"
        f"Thanks for shopping with VULOR — you're the real MVP.\n"
        f"— VULOR Team"
    )
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_order_cancelled(user, order):
    subject = f"VULOR Order #{order.id} Cancelled"
    message = (
        f"Hello {user.first_name},\n\n"
        f"Your order has been cancelled.\n"
        f"Order ID: {order.id}\n"
        f"If this wasn’t intentional, reach out asap.\n"
        f"— VULOR Team"
    )
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

def send_payment_receipt(user, order):
    subject = f'Payment Received - {order.id}'
    message = render_to_string('emails/payment_reciept.html', {
    'user': user,
    'order': order
})
    send_mail(subject, message, None, [user.email])

def send_order_status_update(order, old_status):
    subject = f'Shipping Update - {order.id}'
    message = render_to_string('emails/shipping_update.html', {'user': user, 'order': order})
    send_mail(subject, message, None, [user.email])

def send_low_stock_alert(product):
    subject = f'Low Stock Alert - {product.name}'
    message = f'The product "{product.name}" is running low on stock. Current stock: {product.stock}'
    admin_email = 'youradmin@vulor.com'
    send_mail(subject, message, None, [admin_email])

def send_admin_new_order(order):
    subject = f"New Order #{order.id} Placed"
    message = f"Order #{order.id} was placed by {order.user.username} totaling ₦{order.get_total_price}."
    send_mail(subject, message, None, [ADMIN_EMAIL])

def send_admin_order_notification(order):
    subject = f"Order #{order.id} Notification"
    message = f"Order #{order.id} by {order.user.username} requires your attention."
    send_mail(subject, message, None, [ADMIN_EMAIL])

def send_admin_high_value_order(order):
    subject = f"High-Value Order Alert #{order.id}"
    message = f"Order #{order.id} totaling ₦{order.total} requires attention."
    send_mail(subject, message, None, [ADMIN_EMAIL])

def send_admin_order_cancellation(order):
    subject = f"Order #{order.id} Cancelled"
    message = f"Order #{order.id} by {order.user.username} was cancelled."
    send_mail(subject, message, None, [ADMIN_EMAIL])

def send_review_request(user, order):
    subject = f'Review Your Purchase - Order #{order.id}'
    message = render_to_string('emails/review_request.html', {'user': user, 'order': order})
    send_mail(subject, message, None, [user.email])


def send_abandoned_cart_email(user, cart):
    subject = "You left something in your cart!"
    html_content = render_to_string('emails/abandoned_cart.html', {'user': user, 'cart': cart})
    msg = EmailMultiAlternatives(subject, '', 'VULOR <no-reply@vulor.com>', [user.email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

