# payments/views.py
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

# 1) Initiate payment and redirect admin -> paystack (used by server-side flow)
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
    if existing and (datetime.now() - existing.created_at).total_seconds() < 1800:
        payment = existing
    else:
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            paystack_reference=PaymentTransaction.generate_reference(),
            status='pending',
            metadata={'items_count': order.items.count()}
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
@login_required
def get_payment_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    payment = PaymentTransaction.objects.create(
        order=order,
        amount=order.total_amount,
        paystack_reference=PaymentTransaction.generate_reference(),
        status='pending',
    )
    data = {
        'reference': payment.paystack_reference,
        'amount': payment.amount_in_kobo,
        'email': order.customer_email,
        'public_key': settings.PAYSTACK_PUBLIC_KEY,
        'callback_url': request.build_absolute_uri(reverse('payments:verify_payment')),
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

    if payment.status == 'success':
        return redirect('payments:payment_success', order_id=payment.order.id)

    paystack = PaystackService()
    try:
        verification = paystack.verify_transaction(reference)
    except Exception as e:
        messages.error(request, "Unable to verify payment right now.")
        return redirect('payments:payment_failed', order_id=payment.order.id)

    if verification.get('status') and verification['data']['status'] == 'success':
        # mark payment success
        payment.status = 'success'
        payment.verified_at = datetime.now()
        payment.metadata['verify_data'] = verification['data']
        payment.save()

        # update order
        order = payment.order
        order.payment_status = 'success'
        order.paystack_reference = reference
        order.save()

        # optional: clear cart, send email etc.
        messages.success(request, "Payment completed successfully.")
        return redirect('payments:payment_success', order_id=order.id)
    else:
        payment.status = 'failed'
        payment.metadata['verify_data'] = verification
        payment.save()
        messages.error(request, "Payment verification failed.")
        return redirect('payments:payment_failed', order_id=payment.order.id)


# 4) Webhook handler (Paystack posts here) — secure with HMAC SHA512 signature
@csrf_exempt
@require_POST
def webhook_view(request):
    signature = request.headers.get('x-paystack-signature', '')
    body = request.body

    # verify signature
    webhook_secret = settings.PAYSTACK_WEBHOOK_SECRET
    computed = hmac.new(webhook_secret.encode('utf-8'), body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed, signature):
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    payload = json.loads(body.decode('utf-8'))
    event = payload.get('event')
    data = payload.get('data', {})

    # minimal handling: charge.success & charge.failed
    if event == 'charge.success':
        reference = data.get('reference')
        try:
            payment = PaymentTransaction.objects.get(paystack_reference=reference)
            if payment.status != 'success':
                payment.status = 'success'
                payment.verified_at = datetime.now()
                payment.metadata.setdefault('webhook', {}).update(data)
                payment.save()

                order = payment.order
                order.payment_status = 'success'
                order.paystack_reference = reference
                order.save()
                # Optionally send email here
        except PaymentTransaction.DoesNotExist:
            # log or ignore
            pass
        return JsonResponse({'status': 'ok'})

    if event == 'charge.failed':
        reference = data.get('reference')
        try:
            payment = PaymentTransaction.objects.get(paystack_reference=reference)
            payment.status = 'failed'
            payment.metadata.setdefault('webhook', {}).update(data)
            payment.save()

            order = payment.order
            order.payment_status = 'failed'
            order.save()
        except PaymentTransaction.DoesNotExist:
            pass
        return JsonResponse({'status': 'ok'})

    # default
    return JsonResponse({'status': 'ignored'})

# 5) Success and failure pages
@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/success.html', {'order': order})

@login_required
def payment_failed(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/failed.html', {'order': order})