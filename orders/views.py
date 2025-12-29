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
import logging

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

        if request.method == "POST":
            # Get all form data from template
            full_name = request.POST.get("full_name", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            email = request.POST.get("email", "").strip()
            address_line = request.POST.get("address_line", "").strip()
            state = request.POST.get("state", "").strip()
            city = request.POST.get("city", "").strip()
            shipping_zone = request.POST.get("shipping_zone", "").strip()
            
            # Validate required fields (using template field names)
            required_fields = {
                'full_name': full_name,
                'phone_number': phone_number,
                'email': email,
                'address_line': address_line,
                'state': state,
                'city': city
            }
            
            missing_fields = [field.replace('_', ' ').title() for field, value in required_fields.items() if not value]
            
            if missing_fields:
                messages.error(request, f"Please fill in: {', '.join(missing_fields)}")
                return render(request, "orders/checkout.html", {"cart": cart})
            
            # --- FIX 7: SERVER-SIDE EMAIL VALIDATION ---
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, "Invalid email address.")
                return render(request, "orders/checkout.html", {"cart": cart})

            # --- FIX 7: SERVER-SIDE PHONE VALIDATION ---
            if not phone_number.isdigit() or len(phone_number) < 10:
                messages.error(request, "Invalid phone number.")
                return render(request, "orders/checkout.html", {"cart": cart})


            try:
                # Convert shipping fee to decimal
                from decimal import Decimal
                shipping_fee_decimal = Decimal("0.00")

                if state.lower() == "lagos":
                    shipping_fee_decimal = Decimal("5000.00")
                else:
                    shipping_fee_decimal = Decimal("3000.00")


                # if Order.objects.filter(user=request.user, payment_status='pending').exists():
                #     messages.error(request, "You already have a pending order.")
                #     return redirect('view_cart')
                
                
                calculated_total = cart.total_price + shipping_fee_decimal

                if calculated_total <= 0:
                    messages.error(request, "Order total is less than or equal to zero.")
                    return redirect('view_cart')

                
                # Create order - ONLY map template fields to model fields
                with transaction.atomic():
                    Order.objects.select_for_update().filter(
                        user=request.user,
                        payment_status='pending'
                    )
                    order = Order.objects.create(
                        user=request.user,
                        total_amount=cart.total_price,
                        # Map template fields to model fields
                        shipping_full_name=full_name,
                        shipping_address=address_line,  # address_line -> shipping_address
                        shipping_city=city,  # city -> shipping_city
                        shipping_state=state,  # state -> shipping_state
                        shipping_zipcode="",  # Not in template, set to empty
                        shipping_country="Nigeria",  # Default
                        shipping_fee=shipping_fee_decimal,  # From hidden input
                        shipping_zone=shipping_zone,  # From hidden input
                        customer_email=email,  # email -> customer_email
                        customer_phone=phone_number,  # phone_number -> customer_phone
                    )

                # Create order items from cart items
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                        size=cart_item.size,
                        color=cart_item.color,
                    )

                logger.info(f"Order {order.id} created by {request.user.email}")
                cart.items.all().delete()
                # Redirect to payment initiation
                return redirect('payments:initiate_payment', order_id=order.id)

            except Exception as e:
                logger.info(f"Error creating order {order.id} by {request.user.email}: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Error creating order: {str(e)}")
                return render(request, "orders/checkout.html", {"cart": cart})

        logger.info(f"Checkout page visited by {request.user.email}")
        # GET request - show checkout form
        return render(request, "orders/checkout.html", {"cart": cart})
    
    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty.")
        return redirect("view_cart")
@login_required
def order_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    
    # Only show success if payment was successful
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

