import os

from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit

from .forms import ReceiptUploadForm
from .models import PaymentTransaction
from .utils import get_bank_details
from orders.models import Order
from services.email_service import send_admin_payment_verification

import logging

logger = logging.getLogger(__name__)


def _closed_for_payment(request, order):
    """Redirect response if the order no longer accepts a transfer/receipt,
    else None. Shared by the GET and POST views so they can't drift."""
    if order.payment_status == 'success':
        messages.info(request, "Order already paid.")
    elif order.payment_status == 'pending_verification':
        messages.info(request, "We already received your receipt. Your payment is being verified.")
    else:
        return None
    return redirect('orders:order_detail', order_number=order.order_number)


def _get_or_create_pending_transaction(order):
    payment = PaymentTransaction.objects.latest_for(order, ['pending'])
    if payment is None:
        try:
            # Wrapped in its own atomic() so a constraint violation only
            # rolls back this savepoint, not the whole request's
            # transaction (ATOMIC_REQUESTS=True) — without the savepoint,
            # catching IntegrityError here wouldn't actually leave the
            # connection usable for the recovery query below.
            with transaction.atomic():
                payment = PaymentTransaction.objects.create(
                    order=order,
                    amount=order.grand_total,
                    reference=PaymentTransaction.generate_reference(),
                    status='pending',
                )
        except IntegrityError:
            # Two requests raced to create the first pending transaction for
            # this order (e.g. a double-tap on a slow connection) — the
            # one_active_payment_per_order constraint let exactly one
            # through. Re-fetch the winner instead of letting this 500.
            payment = PaymentTransaction.objects.latest_for(
                order, ['pending', 'pending_verification']
            )
    return payment


def _render_instructions(request, order, payment, form):
    return render(request, 'payments/bank_transfer_instructions.html', {
        'order': order,
        'payment': payment,
        'form': form,
        **get_bank_details(),
    })


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@login_required
def transfer_instructions(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    closed = _closed_for_payment(request, order)
    if closed:
        return closed

    if order.grand_total <= 0:
        messages.error(request, "Invalid order amount.")
        return redirect('view_cart')

    payment = _get_or_create_pending_transaction(order)
    return _render_instructions(request, order, payment, ReceiptUploadForm())


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@login_required
@require_POST
def submit_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    closed = _closed_for_payment(request, order)
    if closed:
        return closed

    payment = _get_or_create_pending_transaction(order)
    form = ReceiptUploadForm(request.POST, request.FILES, instance=payment)

    if not form.is_valid():
        return _render_instructions(request, order, payment, form)

    order.submit_receipt(form.save(commit=False))
    logger.info(f"Receipt uploaded for order {order.order_number} by {request.user.email}")

    try:
        send_admin_payment_verification(order, payment)
    except Exception:
        logger.error(
            f"Failed to send payment verification email for order {order.id}",
            exc_info=True,
        )

    messages.success(
        request,
        "Receipt received. We'll confirm your payment and start processing your order shortly."
    )
    return redirect('orders:order_detail', order_number=order.order_number)


@staff_member_required
def receipt_download(request, txn_id):
    """The only way to reach a stored receipt. Receipts are customer bank
    documents — never link txn.receipt.url directly; always go through here."""
    txn = get_object_or_404(PaymentTransaction, id=txn_id)
    if not txn.receipt:
        raise Http404("No receipt uploaded for this transaction.")
    return FileResponse(
        txn.receipt.open('rb'),
        as_attachment='download' in request.GET,
        filename=os.path.basename(txn.receipt.name),
    )


# Order Tracking (orders:order_detail) is the single canonical result screen —
# it owns the confirmed celebration, the in-review state, and the rejected/retry
# path (Design Review 01 §1.5: one moment, one screen). These legacy result URLs
# are kept so any old link still resolves, but they now redirect to that page
# instead of rendering duplicate celebration templates.
@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return redirect('orders:order_detail', order_number=order.order_number)


@login_required
def payment_failed(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return redirect('orders:order_detail', order_number=order.order_number)
