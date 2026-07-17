# dashboard/views.py was split into this package (home/reviews/orders/
# products/customers) purely for file-size/organization reasons — no
# function was changed. Re-exporting everything here means dashboard/urls.py
# ("from . import views", then "views.dashboard_home" etc.) keeps working
# unchanged; only this file needed to know the new internal layout.
from .home import dashboard_home, new_orders_check, new_orders_ack
from .reviews import review_list, delete_review, approve_review
from .orders import order_list, confirm_payment, reject_payment, update_order_status
from .products import (
    product_list,
    add_product,
    edit_product,
    delete_product,
    delete_alternate_image,
    set_main_alternate_image,
)
from .customers import customer_list, edit_customer, toggle_user_active

__all__ = [
    "dashboard_home",
    "new_orders_check",
    "new_orders_ack",
    "review_list",
    "delete_review",
    "approve_review",
    "order_list",
    "confirm_payment",
    "reject_payment",
    "update_order_status",
    "product_list",
    "add_product",
    "edit_product",
    "delete_product",
    "delete_alternate_image",
    "set_main_alternate_image",
    "customer_list",
    "edit_customer",
    "toggle_user_active",
]
