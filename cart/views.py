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


@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def add_to_cart(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart, created = Cart.objects.get_or_create(user=request.user)

        quantity = int(request.POST.get('quantity', 1))

        default_sizes = product.get_available_sizes_list()
        default_colors = product.get_available_colors_list()
        size = request.POST.get('size', '').strip() or (default_sizes[0] if default_sizes else '')
        color = request.POST.get('color', '').strip() or (default_colors[0] if default_colors else '')

        if quantity > 100:
            messages.error(request, "You cannot add more than 100 of a single item.")
            return redirect('view_cart')

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, size=size, color=color,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        logger.info(f"User {request.user.email} added {quantity} x {product.name} to cart.")
        messages.success(request, f'Added {product.name} to cart!')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'cart_total_items': cart.total_items})
        return redirect('product_detail', slug=product.slug)

    return redirect('product_list')


@ratelimit(key='ip', rate='20/m', block=True)
@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    product_name = cart_item.product.name
    cart_item.delete()
    logger.info(f"User {request.user.email} removed {product_name} from cart.")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    messages.info(request, f'Removed {product_name} from cart.')
    return redirect('view_cart')


@login_required
def update_cart_item(request, item_id):
    if request.method != 'POST':
        return redirect('view_cart')

    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            raise ValueError
    except ValueError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Invalid quantity'}, status=400)
        messages.error(request, 'Invalid quantity specified.')
        return redirect('view_cart')

    cart_item.quantity = quantity
    cart_item.save()
    logger.info(f"User {request.user.email} updated {cart_item.product.name} quantity to {quantity}.")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('view_cart')