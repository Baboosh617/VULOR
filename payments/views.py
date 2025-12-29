import json
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import PaymentTransaction
from .services.paystack_service import PaystackService
from orders.models import Order

from django.urls import reverse
from django.utils import timezone

from cart.models import CartItem, Cart
from django.db import transaction
from django_ratelimit.decorators import ratelimit
import logging

logger = logging.getLogger(__name__)
# 1) Initiate payment and redirect admin -> paystack (used by server-side flow)
@ratelimit(key='user_or_ip', rate='5/m', block=True)
@login_required
def initiate_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # basic validations
    if order.payment_status == 'success':
        messages.info(request, "Order already paid.")
        return redirect('orders:order_detail', order_number=order.order_number)

    if order.total_amount <= 0:
        messages.error(request, "Invalid order amount.")
        return redirect('cart:view_cart')

    # reuse recent pending transaction if exists (optional)
    existing = PaymentTransaction.objects.filter(order=order, status__in=['pending', 'initiated']).order_by('-created_at').first()
    if existing and (timezone.now() - existing.created_at).total_seconds() < 1800:
        payment = existing
    else:
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount + order.shipping_fee, 
            paystack_reference=PaymentTransaction.generate_reference(),
            status='pending',
            metadata={'items_count': order.items.count(), 'delivery_fee': float(order.shipping_fee)}
        )

    paystack = PaystackService()
    callback_url = request.build_absolute_uri(reverse('payments:verify_payment'))

    try:
        response = paystack.initialize_transaction(
            email=order.customer_email,
            amount=payment.amount_in_kobo,    # kobo
            reference=payment.paystack_reference,
            callback_url=callback_url,
            metadata={
                "order_id": order.id,
                "payment_id": payment.id
            }
        )
    except Exception as e:
        # network or API error
        payment.status = 'failed'
        payment.metadata['init_error'] = str(e)
        payment.save()
        messages.error(request, "Payment service temporarily unavailable.")
        return redirect('payments:payment_failed', order_id=order.id)

    # process paystack response
    data = response.get('data') or {}
    if response.get('status') and data.get('authorization_url'):
        payment.paystack_access_code = data.get('access_code', '')
        payment.status = 'initiated'
        payment.metadata['paystack_init'] = data
        payment.save()
        return redirect(data['authorization_url'])
    else:
        payment.status = 'failed'
        payment.metadata['paystack_init_error'] = response
        payment.save()
        messages.error(request, "Could not start payment. Try again.")
        return redirect('payments:payment_failed', order_id=order.id)

# 2) API endpoint for front-end JS integration (optional)
@ratelimit(key='user_or_ip', rate='5/m', block=True)
@login_required
def get_payment_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Reuse recent pending transaction
    existing = (
        PaymentTransaction.objects
        .filter(order=order, status__in=['pending', 'initiated'])
        .order_by('-created_at')
        .first()
    )

    if existing and (timezone.now() - existing.created_at).total_seconds() < 1800:
        payment = existing
    else:
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            paystack_reference=PaymentTransaction.generate_reference(),
            status='pending',
            metadata={'items_count': order.items.count()}
        )

    data = {
        'reference': payment.paystack_reference,
        'amount': payment.amount_in_kobo,
        'email': order.customer_email,
        'public_key': settings.PAYSTACK_PUBLIC_KEY,
        'callback_url': request.build_absolute_uri(
            reverse('payments:verify_payment')
        ),
    }

    return JsonResponse({'status': 'success', 'data': data})



# 3) Verify view — Paystack redirects here after payment
@login_required
@require_GET
def verify_payment(request):
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, "No payment reference provided.")
        return redirect('cart:view_cart')

    try:
        payment = PaymentTransaction.objects.get(paystack_reference=reference)
    except PaymentTransaction.DoesNotExist:
        messages.error(request, "Payment not found.")
        return redirect('cart:view_cart')

    with transaction.atomic():
        payment = PaymentTransaction.objects.select_for_update().get(
            paystack_reference=reference
        )

        if payment.status == 'success':
            return redirect('payments:payment_success', order_id=payment.order.id)

        if payment.status == 'failed':
            messages.error(request, "Payment failed.")
            return redirect('payments:payment_failed', order_id=payment.order.id)



    paystack = PaystackService()
    try:
        verification = paystack.verify_transaction(reference)
        txn = payment  # clarity

        expected_kobo = txn.amount_in_kobo
        paid_kobo = verification['data']['amount']
        
        if paid_kobo != expected_kobo:
            txn.status = 'failed'
            txn.metadata['amount_mismatch'] = {
                'expected': expected_kobo,
                'paid': paid_kobo
            }
            txn.save()
        
            logger.warning(
                "PAYMENT AMOUNT MISMATCH",
                extra={
                    'order_id': txn.order.id,
                    'expected': expected_kobo,
                    'paid': paid_kobo,
                    'reference': reference
                }
            )
            return HttpResponse("Amount mismatch", status=400)
        
    except Exception as e:
        messages.info(
            request,
            "Payment received. Confirmation is pending. You will be updated shortly."
        )
        return redirect('orders:order_detail', order_number=payment.order.order_number)

    data = verification.get("data", {})
    meta = data.get("metadata", {})
    if meta.get("order_id") and str(meta["order_id"]) != str(payment.order.id):
        return HttpResponse("Order mismatch", status=400)


    if verification.get('status') and verification['data']['status'] == 'success':
        # mark payment success
        payment.status = 'success'
        payment.verified_at = timezone.now()
        payment.metadata['verify_data'] = verification['data']
        payment.save()

        # update order
        order = payment.order
        order.payment_status = 'success'
        order.paystack_reference = reference
        order.save()

        # optional: clear cart, send email etc.
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            CartItem.objects.filter(cart=cart).delete()

        messages.success(request, "Payment completed successfully.")
        return redirect('payments:payment_success', order_id=order.id)
        
    if verification['data']['status'] == 'failed':
        payment.status = 'failed'
        payment.metadata['verify_data'] = verification
        payment.save()
        messages.error(request, "Payment failed.")
        return redirect('payments:payment_failed', order_id=payment.order.id)

    # otherwise treat as pending
    messages.info(
        request,
        "Payment is being confirmed. You will be updated shortly."
    )
    return redirect('orders:order_detail', order_number=payment.order.order_number)

    
    


# 4) Webhook handler (Paystack posts here) — secure with HMAC SHA512 signature
@csrf_exempt
@require_POST
def paystack_webhook(request):
    payload = request.body
    signature = request.headers.get("x-paystack-signature")

    expected_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        payload,
        hashlib.sha512
    ).hexdigest()

    if signature != expected_signature:
        return HttpResponse(status=400)
    try:
        event = json.loads(payload)
    except ValueError:
        return HttpResponse(status=400)
    data = event.get("data", {})

    if event.get("event") != "charge.success":
        return HttpResponse(status=200)

    if data.get("currency") != "NGN":
        return HttpResponse(status=200)

    reference = data.get("reference")
    if not reference:
        return HttpResponse(status=400)

    try:
        with transaction.atomic():
            txn = PaymentTransaction.objects.select_for_update().get(
                paystack_reference=reference
            )

            if txn.status == "success":
                return HttpResponse(status=200)

            paid_kobo = data.get("amount")
            expected_kobo = txn.amount_in_kobo

            if paid_kobo != expected_kobo:
                logger.warning("Webhook amount mismatch", extra={
                    "reference": reference,
                    "expected": expected_kobo,
                    "paid": paid_kobo,
                })
                return HttpResponse(status=400)

            meta = data.get("metadata", {})
            if str(meta.get("order_id")) != str(txn.order.id):
                return HttpResponse(status=400)

            # MARK PAYMENT SUCCESS
            txn.status = "success"
            txn.verified_at = timezone.now()
            txn.metadata = txn.metadata or {}
            txn.metadata["webhook_data"] = data
            txn.save()

            # UPDATE ORDER
            order = txn.order
            order.payment_status = "success"
            order.paystack_reference = reference
            order.save()

            # CLEAR CART
            cart = Cart.objects.filter(user=order.user).first()
            if cart:
                CartItem.objects.filter(cart=cart).delete()

    except PaymentTransaction.DoesNotExist:
        return HttpResponse(status=200)

    return HttpResponse(status=200)
    
# Success and failure pages
@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/success.html', {'order': order})

@login_required
def payment_failed(request, order_id): 
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/payment_failed.html', {'order': order})