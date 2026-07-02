from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import Order, OrderItem
from cart.models import Cart
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
import logging

User = get_user_model()

logger = logging.getLogger(__name__)

@ratelimit(key='user_or_ip', rate='10/m', block=True)
@login_required
@require_POST
def checkout(request):
    logger.info(f"User {request.user.email} is checking out.")
    try:
        cart = get_object_or_404(Cart, user=request.user)

        if not cart.items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("view_cart")

        full_name = request.POST.get("full_name", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        email = request.POST.get("email", "").strip()
        address_line = request.POST.get("address_line", "").strip()
        state = request.POST.get("state", "").strip()
        city = request.POST.get("city", "").strip()
        shipping_zone = request.POST.get("shipping_zone", "").strip()

        required_fields = {
            'full_name': full_name, 'phone_number': phone_number, 'email': email,
            'address_line': address_line, 'state': state, 'city': city,
        }
        missing_fields = [f.replace('_', ' ').title() for f, v in required_fields.items() if not v]
        if missing_fields:
            messages.error(request, f"Please fill in: {', '.join(missing_fields)}")
            return render(request, "orders/checkout.html", {"cart": cart})

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email address.")
            return render(request, "orders/checkout.html", {"cart": cart})

        if not phone_number.isdigit() or len(phone_number) < 10:
            messages.error(request, "Invalid phone number.")
            return render(request, "orders/checkout.html", {"cart": cart})

        try:
            from decimal import Decimal
            shipping_fee_decimal = Decimal("5000.00") if state.lower() == "lagos" else Decimal("3000.00")

            # fast-fail before touching the lock — optimization only, not the
            # authoritative check (see inside the atomic block below)
            if Order.objects.filter(user=request.user, payment_status='pending').exists():
                messages.error(request, "You already have a pending order.")
                return redirect('view_cart')

            calculated_total = cart.total_price + shipping_fee_decimal
            if calculated_total <= 0:
                messages.error(request, "Order total is less than or equal to zero.")
                return redirect('view_cart')

            # ---- THIS replaces the old dead `Order.objects.select_for_update().filter(...)` ----
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
                    shipping_full_name=full_name,
                    shipping_address=address_line,
                    shipping_city=city,
                    shipping_state=state,
                    shipping_zipcode="",
                    shipping_country="Nigeria",
                    shipping_fee=shipping_fee_decimal,
                    shipping_zone=shipping_zone,
                    customer_email=email,
                    customer_phone=phone_number,
                )
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order, product=cart_item.product, quantity=cart_item.quantity,
                        price=cart_item.product.price, size=cart_item.size, color=cart_item.color,
                    )
                logger.info(f"Order {order.id} created by {request.user.email}")
                cart.items.all().delete()

            return redirect('payments:initiate_payment', order_id=order.id)

        except Exception as e:
            logger.error(f"Error creating order for user {request.user.email}: {str(e)}", exc_info=True)
            messages.error(request, "Something went wrong while creating your order. Please try again.")
            return render(request, "orders/checkout.html", {"cart": cart})

    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty.")
        return redirect("view_cart")
@login_required
def order_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    
    
    if order.payment_status != 'success':
        messages.warning(request, "Payment not completed yet.")
        return redirect('orders:order_detail', order_number=order.order_number)
    
    return render(request, 'orders/success.html', {'order': order})

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

