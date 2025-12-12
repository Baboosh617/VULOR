from .models import Cart

def cart_context(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return {
            'cart_total_items': cart.total_items,
            'cart_total_price': cart.total_price,
        }
    return {
        'cart_total_items': 0,
        'cart_total_price': 0,
    }