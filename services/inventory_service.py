from django.db import transaction
from django.db.models import F
from products.models import Product

def reduce_inventory(order):
    """Raises ValueError if any line item can't be fully covered by current
    stock — the conditional filter means the UPDATE simply matches zero rows
    rather than going negative, so we check the affected count explicitly."""
    with transaction.atomic():
        for item in order.items.all():
            updated = Product.objects.filter(
                id=item.product.id, inventory_count__gte=item.quantity
            ).update(inventory_count=F("inventory_count") - item.quantity)
            if updated == 0:
                raise ValueError(
                    f"Insufficient stock for product {item.product.id} "
                    f"(order {order.id}, needed {item.quantity})"
                )

def restock_order_items(order):
    with transaction.atomic():
        for item in order.items.all():
            Product.objects.filter(id=item.product.id).update(
                inventory_count=F("inventory_count") + item.quantity
            )
