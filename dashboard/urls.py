from django.urls import path
from . import views

app_name="dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/<int:review_id>/approve/", views.approve_review, name="approve_review"),
    path("reviews/<int:review_id>/delete/", views.delete_review, name="delete_review"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:order_id>/update-status/", views.update_order_status, name="update_order_status"),
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.add_product, name="add_product"),
    path("products/<int:product_id>/edit/", views.edit_product, name="edit_product"),
    path("products/<int:product_id>/delete/", views.delete_product, name="delete_product"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:user_id>/toggle-active/", views.toggle_user_active, name="toggle_user_active"),
    path("customers/<int:user_id>/edit/", views.edit_customer, name="edit_customer"),
]
