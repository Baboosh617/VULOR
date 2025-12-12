from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import Order, OrderItem
from cart.models import Cart

@login_required
def checkout(request):
    try:
        cart = get_object_or_404(Cart, user=request.user)
        
        if not cart.items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("cart:view_cart")

        if request.method == "POST":
            # Validate required shipping fields
            required_fields = ['shipping_address', 'shipping_city', 'shipping_state', 'shipping_zipcode', 'customer_phone']
            missing_fields = [field.replace('_', ' ').title() for field in required_fields if not request.POST.get(field)]
            
            if missing_fields:
                messages.error(request, f"Please fill in: {', '.join(missing_fields)}")
                return render(request, "orders/checkout.html", {"cart": cart})

            try:
                # Create order
                order = Order.objects.create(
                    user=request.user,
                    total_amount=cart.total_price,
                    shipping_address=request.POST.get("shipping_address"),
                    shipping_city=request.POST.get("shipping_city"),
                    shipping_state=request.POST.get("shipping_state"),
                    shipping_zipcode=request.POST.get("shipping_zipcode"),
                    shipping_country=request.POST.get("shipping_country", "Nigeria"),
                    customer_email=request.user.email,
                    customer_phone=request.POST.get("customer_phone", ""),
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

                print(f"✅ Order created: {order.id}")
                
                # Redirect to payment initiation
                return redirect('payments:initiate_payment', order_id=order.id)

            except Exception as e:
                print(f"❌ Order creation error: {e}")
                messages.error(request, f"Error creating order: {str(e)}")
                return render(request, "orders/checkout.html", {"cart": cart})

        # GET request - show checkout form
        return render(request, "orders/checkout.html", {"cart": cart})
    
    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty.")
        return redirect("cart:view_cart")
@login_required
def order_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    
    # Only show success if payment was successful
    if order.payment_status != 'success':
        messages.warning(request, "Payment not completed yet.")
        return redirect('orders:order_detail', order_number=order.order_number)
    
    return render(request, 'orders/success.html', {'order': order})

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/history.html', {'orders': orders})

@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    return render(request, 'orders/detail.html', {'order': order})

