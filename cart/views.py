# cart/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Cart, CartItem
from products.models import Product
from django_ratelimit.decorators import ratelimit
import logging

logger = logging.getLogger(__name__)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def view_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart/cart.html', {'cart': cart})


@ratelimit(key='ip', rate='30/m', block=True)
@login_required
def add_to_cart(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart, _ = Cart.objects.get_or_create(user=request.user)

    quantity = int(request.POST.get('quantity', 1))
    size     = request.POST.get('size', '')
    color    = request.POST.get('color', '')

    if quantity > 100:
        if _is_ajax(request):
            return JsonResponse({'success': False, 'message': 'Maximum quantity is 100'})
        messages.error(request, 'Maximum quantity is 100')
        return redirect('view_cart')

    # Check stock
    if product.inventory_count < quantity:
        if _is_ajax(request):
            return JsonResponse({'success': False, 'message': 'Not enough stock available'})
        messages.error(request, 'Not enough stock available')
        return redirect('product_detail', slug=product.slug)

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

    logger.info(f"User {request.user.email} added {quantity}x {product.name} to cart")

    if _is_ajax(request):
        return JsonResponse({
            'success': True,
            'message': f'{product.name} added to cart',
            'cart_count': cart.total_items,
            'cart_total': str(cart.total_price),
        })

    messages.success(request, f'{product.name} added to cart!')
    return redirect('product_detail', slug=product.slug)


@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart      = cart_item.cart
    product_name = cart_item.product.name
    cart_item.delete()

    logger.info(f"User {request.user.email} removed {product_name} from cart")

    if _is_ajax(request):
        return JsonResponse({
            'success': True,
            'message': f'{product_name} removed',
            'cart_count': cart.total_items,
            'subtotal':   str(cart.total_price),
        })

    messages.info(request, f'{product_name} removed from cart')
    return redirect('view_cart')


@login_required
def update_cart_item(request, item_id):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)

    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart      = cart_item.cart

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            raise ValueError
    except (ValueError, TypeError):
        if _is_ajax(request):
            return JsonResponse({'success': False, 'message': 'Invalid quantity'})
        messages.error(request, 'Invalid quantity')
        return redirect('view_cart')

    item_total = None
    if quantity > 0:
        cart_item.quantity = quantity
        cart_item.save()
        item_total = str(cart_item.total_price)
    else:
        cart_item.delete()

    logger.info(f"User {request.user.email} updated cart item {item_id} to qty {quantity}")

    if _is_ajax(request):
        return JsonResponse({
            'success': True,
            'cart_count': cart.total_items,
            'subtotal':   str(cart.total_price),
            'item_total': item_total,
        })

    return redirect('view_cart')