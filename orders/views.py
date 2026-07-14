from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Order, OrderItem
from .forms import CheckoutForm
from .shipping import get_shipping_info, client_table
from cart.models import Cart
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.contrib.auth import get_user_model
import logging

User = get_user_model()

logger = logging.getLogger(__name__)


def _render_checkout(request, cart):
    return render(request, "orders/checkout.html", {
        "cart": cart,
        "shipping_zones": client_table(),
    })


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    if not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("view_cart")

    if request.method != "POST":
        return _render_checkout(request, cart)

    logger.info(f"User {request.user.email} is checking out.")

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            label = field.replace('_', ' ').title()
            messages.error(request, f"{label}: {errors[0]}")
        return _render_checkout(request, cart)

    cd = form.cleaned_data
    # Fee and zone come from the server-side table, never from the client.
    shipping_zone, shipping_fee = get_shipping_info(cd["state"])

    try:
        # fast-fail before touching the lock — optimization only, not the
        # authoritative check (see inside the atomic block below)
        if Order.objects.filter(user=request.user, payment_status='pending').exists():
            messages.error(request, "You already have a pending order.")
            return redirect('view_cart')

        if cart.total_price + shipping_fee <= 0:
            messages.error(request, "Order total is less than or equal to zero.")
            return redirect('view_cart')

        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)

            # authoritative recheck — the row lock above serializes concurrent
            # requests from the same user, so this check is now race-safe
            if Order.objects.filter(user=request.user, payment_status='pending').exists():
                messages.error(request, "You already have a pending order.")
                return redirect('view_cart')

            order = Order.objects.create(
                user=request.user,
                total_amount=cart.total_price,
                shipping_full_name=cd["full_name"],
                shipping_address=cd["address_line"],
                shipping_city=cd["city"],
                shipping_state=cd["state"],
                shipping_zipcode="",
                shipping_country="Nigeria",
                shipping_fee=shipping_fee,
                shipping_zone=shipping_zone,
                customer_email=cd["email"],
                customer_phone=cd["phone_number"],
                order_notes=cd["order_notes"],
            )
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order, product=cart_item.product, quantity=cart_item.quantity,
                    price=cart_item.product.price, size=cart_item.size, color=cart_item.color,
                )
            logger.info(f"Order {order.id} created by {request.user.email}")
            cart.items.all().delete()

        return redirect('payments:transfer_instructions', order_id=order.id)

    except Exception:
        logger.error(f"Error creating order for user {request.user.email}", exc_info=True)
        messages.error(request, "Something went wrong while creating your order. Please try again.")
        return _render_checkout(request, cart)


@login_required
def order_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    if order.payment_status != 'success':
        messages.warning(request, "Payment not completed yet.")
        return redirect('orders:order_detail', order_number=order.order_number)

    return render(request, 'payments/success.html', {'order': order})


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/history.html', {'orders': orders})


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    return render(request, 'orders/detail.html', {'order': order})
