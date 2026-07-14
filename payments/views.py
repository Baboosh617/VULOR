from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from .forms import ReceiptUploadForm
from .models import PaymentTransaction
from orders.models import Order
from services.email_service import send_admin_payment_verification

import logging

logger = logging.getLogger(__name__)


def _bank_details():
    return {
        'bank_name': settings.BANK_TRANSFER_BANK_NAME,
        'account_name': settings.BANK_TRANSFER_ACCOUNT_NAME,
        'account_number': settings.BANK_TRANSFER_ACCOUNT_NUMBER,
    }


def _get_or_create_pending_transaction(order):
    payment = (
        PaymentTransaction.objects
        .filter(order=order, status__in=['pending', 'initiated'])
        .order_by('-created_at')
        .first()
    )
    if payment is None:
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.grand_total,
            reference=PaymentTransaction.generate_reference(),
            status='pending',
            metadata={'items_count': order.items.count(), 'delivery_fee': float(order.shipping_fee)},
        )
    return payment


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@login_required
def transfer_instructions(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.payment_status == 'success':
        messages.info(request, "Order already paid.")
        return redirect('orders:order_detail', order_number=order.order_number)

    if order.payment_status == 'pending_verification':
        messages.info(request, "We already received your receipt. Your payment is being verified.")
        return redirect('orders:order_detail', order_number=order.order_number)

    if order.grand_total <= 0:
        messages.error(request, "Invalid order amount.")
        return redirect('view_cart')

    payment = _get_or_create_pending_transaction(order)

    return render(request, 'payments/bank_transfer_instructions.html', {
        'order': order,
        'payment': payment,
        'form': ReceiptUploadForm(),
        **_bank_details(),
    })


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@login_required
@require_POST
def submit_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.payment_status == 'success':
        messages.info(request, "Order already paid.")
        return redirect('orders:order_detail', order_number=order.order_number)

    if order.payment_status == 'pending_verification':
        messages.info(request, "We already received your receipt. Your payment is being verified.")
        return redirect('orders:order_detail', order_number=order.order_number)

    payment = _get_or_create_pending_transaction(order)
    form = ReceiptUploadForm(request.POST, request.FILES, instance=payment)

    if not form.is_valid():
        return render(request, 'payments/bank_transfer_instructions.html', {
            'order': order,
            'payment': payment,
            'form': form,
            **_bank_details(),
        })

    with transaction.atomic():
        payment = form.save(commit=False)
        payment.status = 'pending_verification'
        payment.submitted_at = timezone.now()
        payment.save()

        order.payment_status = 'pending_verification'
        order.save(update_fields=['payment_status', 'updated_at'])

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


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/success.html', {'order': order})

@login_required
def payment_failed(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/payment_failed.html', {'order': order})
