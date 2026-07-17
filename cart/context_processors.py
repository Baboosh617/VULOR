from .models import Cart


def cart_context(request):
    """Runs on every page render for every logged-in user, so this must stay
    cheap. Fetching the cart's items once (with their products prefetched)
    and summing both totals from that single list avoids re-querying twice
    (previously one query per `cart.total_items`/`cart.total_price` property
    access) plus one query per item for `item.product.price`."""
    if not request.user.is_authenticated:
        return {
            'cart_total_items': 0,
            'cart_total_price': 0,
        }

    cart, _ = Cart.objects.prefetch_related('items__product').get_or_create(user=request.user)
    items = list(cart.items.all())
    return {
        'cart_total_items': sum(item.quantity for item in items),
        'cart_total_price': sum(item.total_price for item in items),
    }
