from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Cart, CartItem
from products.models import Product
from django_ratelimit.decorators import ratelimit
import logging

logger = logging.getLogger(__name__)

@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def view_cart(request): 
    cart, created = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart/cart.html', {'cart': cart})

@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def add_to_cart(request, product_id):
    
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        quantity = int(request.POST.get('quantity', 1))
        size = request.POST.get('size', '')
        color = request.POST.get('color', '')

        if quantity > 100:
            messages.error(request, "You cannot add more than 100 of a single item.")
            return redirect('view_cart')

        
        # Check if item already exists in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            size=size,
            color=color,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        logger.info(f"User {request.user.email} added {quantity} x {product.name} to cart.")
        
        messages.success(request, f'Added {product.name} to cart!')
        return redirect('product_detail', slug=product.slug)
    
    return redirect('product_list')

@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    product_name = cart_item.product.name
    cart_item.delete()

    logger.info(f"User {request.user.email} removed {product_name} from cart.")
    messages.info(request, f'Removed {product_name} from cart.')
    return redirect('view_cart')  

@login_required
def update_cart_item(request, item_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

        try:
            quantity = int(request.POST.get('quantity', 1))
            if quantity < 1:
                raise ValueError
        except ValueError:
            messages.error(request, 'Invalid quantity specified.')
            return redirect('view_cart')
        
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
        
        return redirect('view_cart')  
    logger.info(f"User {request.user.email} updated {cart_item.product.name} quantity to {quantity}.")
    return redirect('view_cart')  