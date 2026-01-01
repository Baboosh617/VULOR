from django.db import transaction
from django.db.models import F
from products.models import Product

def reduce_inventory(order):
    with transaction.atomic():
        for item in order.items.all():
            Product.objects.filter(id=item.product.id).update(
                inventory_count=F("inventory_count") - item.quantity
            )

def restock_order_items(order):
    with transaction.atomic():
        for item in order.items.all():
            Product.objects.filter(id=item.product.id).update(
                inventory_count=F("inventory_count") + item.quantity
            )
