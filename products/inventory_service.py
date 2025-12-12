from products.models import Product

def restock_order_items(order):
    """
    Returns items to inventory when an order is cancelled or payment fails.
    """
    for item in order.items.all():
        product = item.product
        product.stock += item.quantity
        product.save(update_fields=["stock"])
