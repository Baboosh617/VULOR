from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
import logging

from orders.models import Order

logger = logging.getLogger(__name__)


@staff_member_required
def order_list(request):
    # orders.html reads order.user.username per row (desktop table and
    # mobile card layout both) — select_related avoids a query per order.
    orders = (
        Order.objects.all()
        .order_by("-created_at")
        .select_related("user")
        .prefetch_related("paymenttransaction_set")
    )

    query = request.GET.get("q")
    if query:
        orders = orders.filter(user__username__icontains=query)

    status_filter = request.GET.get("status")
    if status_filter in ["pending", "completed", "processing", "shipped", "cancelled"]:
        orders = orders.filter(status=status_filter)

    payment_filter = request.GET.get("payment")
    if payment_filter in dict(Order.PAYMENT_STATUS_CHOICES):
        orders = orders.filter(payment_status=payment_filter)

    return render(request, "dashboard/orders.html", {
        "orders": orders,
        "query": query,
        "status_filter": status_filter,
        "payment_filter": payment_filter,
    })


@staff_member_required
@require_POST
def confirm_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.payment_status == "success":
        messages.info(request, f"Order {order.order_number} is already marked paid.")
        return redirect("dashboard:order_list")

    order.confirm_payment()

    logger.info(f"Payment for order {order.order_number} confirmed by {request.user.username}")
    messages.success(request, f"Payment for order {order.order_number} confirmed.")
    return redirect("dashboard:order_list")


@staff_member_required
@require_POST
def reject_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.payment_status != "pending_verification":
        messages.error(request, f"Order {order.order_number} has no receipt awaiting verification.")
        return redirect("dashboard:order_list")

    reason = request.POST.get("rejection_reason", "").strip()
    order.reject_payment(reason=reason)

    logger.info(f"Payment for order {order.order_number} rejected by {request.user.username}")
    messages.success(request, f"Payment for order {order.order_number} rejected. The customer can retry.")
    return redirect("dashboard:order_list")


@staff_member_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status', None)

    status_cycle = ['pending', 'processing', 'shipped', 'completed']

    if new_status and new_status in dict(Order.STATUS_CHOICES):
        order.status = new_status
    else:
        # Cycle to the next status if no specific status provided
        try:
            current_index = status_cycle.index(order.status)
            order.status = status_cycle[(current_index + 1) % len(status_cycle)]
        except ValueError:
            order.status = 'pending'

    order.save()
    logger.info(f"Order {order.id} status updated to {order.status} by {request.user.username}")
    messages.success(request, f"Order #{order.id} updated to {order.status}.")
    return redirect("dashboard:order_list")
