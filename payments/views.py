import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages

from django.urls import reverse
from datetime import timezone

from orders.models import Order
from .models import PaymentTransaction
from .services.paystack_service import PaystackService

from datetime import datetime
import json
import hmac
import hashlib


login_required
def initiate_payment(request, order_id):
    """
    Initiate Paystack payment for an order
    URL: /payments/initiate/<order_id>/
    """
    
    # ==================== 1. GET ORDER & VALIDATE ====================
    try:
        order = Order.objects.select_related('user').get(
            id=order_id, 
            user=request.user
        )
    except Order.DoesNotExist:
        messages.error(request, "Order not found or you don't have permission.")
        return redirect('cart:view_cart')
    
    # Check if order is already paid
    if order.payment_status == 'success':
        messages.info(request, f"Order #{order.order_number} is already paid.")
        return redirect('orders:order_detail', order_number=order.order_number)
    
    # Check if order has items
    if not order.items.exists():
        messages.error(request, "Cannot process payment for an empty order.")
        return redirect('cart:view_cart')
    
    # Check if order total is valid
    if order.total_amount <= 0:
        messages.error(request, "Invalid order amount.")
        return redirect('cart:view_cart')
    
    print(f"🔄 INITIATING PAYMENT: Order #{order.order_number}, Amount: ₦{order.total_amount}")
    
    # ==================== 2. CREATE/GET PAYMENT TRANSACTION ====================
    # Check for existing pending transaction (for retries)
    existing_payment = PaymentTransaction.objects.filter(
        order=order,
        status__in=['pending', 'initiated']
    ).order_by('-created_at').first()
    
    if existing_payment and existing_payment.created_at > timezone.now() - timezone.timedelta(minutes=30):
        # Reuse recent pending transaction
        payment = existing_payment
        print(f"♻️ Reusing existing payment: {payment.paystack_reference}")
    else:
        # Create new payment transaction
        payment = PaymentTransaction.objects.create(
            order=order,
            user=request.user,
            amount=order.total_amount,
            paystack_reference=PaymentTransaction.generate_reference(),
            ip_address=get_client_ip(request),
            metadata={
                'order_number': order.order_number,
                'customer_email': order.customer_email,
                'customer_phone': order.customer_phone or '',
                'items_count': order.items.count(),
                'shipping_to': f"{order.shipping_city}, {order.shipping_state}",
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
            }
        )
        print(f"✅ Created new payment: {payment.paystack_reference}")
    
    # ==================== 3. PREPARE PAYSTACK REQUEST ====================
    paystack_service = PaystackService()
    
    # Build callback URL
    callback_url = request.build_absolute_uri(
        reverse('payments:verify_payment')
    )
    
    # Prepare metadata for Paystack
    metadata = {
        'custom_fields': [
            {
                'display_name': "Order Number",
                'variable_name': "order_number",
                'value': order.order_number
            },
            {
                'display_name': "Customer Name",
                'variable_name': "customer_name",
                'value': request.user.get_full_name() or request.user.username
            }
        ],
        'order_id': order.id,
        'user_id': request.user.id,
        'payment_id': payment.id,
        'items_count': order.items.count(),
    }
    
    # ==================== 4. INITIALIZE PAYSTACK TRANSACTION ====================
    try:
        response = paystack_service.initialize_transaction(
            email=order.customer_email,
            amount=float(order.total_amount),
            reference=payment.paystack_reference,
            callback_url=callback_url,
            metadata=metadata
        )
        
        print(f"📡 Paystack Response: {json.dumps(response, indent=2)}")
        
    except Exception as e:
        print(f"❌ Paystack API Error: {str(e)}")
        payment.status = 'failed'
        payment.metadata['error'] = str(e)
        payment.save()
        
        messages.error(request, "Payment service is currently unavailable. Please try again later.")
        return redirect('payments:payment_failed', order_id=order.id)
    
    # ==================== 5. PROCESS PAYSTACK RESPONSE ====================
    if response.get('status') and response['data'].get('authorization_url'):
        # SUCCESS - Save access code and redirect to Paystack
        
        payment.paystack_access_code = response['data'].get('access_code', '')
        payment.status = 'initiated'
        payment.metadata['paystack_response'] = response['data']
        payment.save()
        
        authorization_url = response['data']['authorization_url']
        
        print(f"🔗 Redirecting to Paystack: {authorization_url}")
        
        # You can also store this in session for tracking
        request.session['current_payment_reference'] = payment.paystack_reference
        request.session['current_order_id'] = order.id
        
        # Redirect to Paystack payment page
        return redirect(authorization_url)
        
    else:
        # FAILED - Handle error
        payment.status = 'failed'
        payment.metadata['error_response'] = response
        payment.save()
        
        # Extract error message
        error_msg = response.get('message', 'Payment initialization failed')
        
        # User-friendly error messages
        error_messages = {
            'Invalid amount': 'The order amount is invalid.',
            'Invalid email': 'The email address is invalid.',
            'Duplicate reference': 'A payment is already in progress for this order.',
        }
        
        user_message = error_messages.get(error_msg, f"Payment Error: {error_msg}")
        
        messages.error(request, user_message)
        
        # Log detailed error for debugging
        print(f"❌ Payment Initiation Failed: {error_msg}")
        print(f"📋 Full response: {json.dumps(response, indent=2)}")
        
        return redirect('payments:payment_failed', order_id=order.id)


def get_client_ip(request):
    """Get the client's IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def payment_instructions(request, order_id):
    """
    Optional: Show payment instructions page before redirecting to Paystack
    URL: /payments/instructions/<order_id>/
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Paystack test card info
    test_cards = [
        {
            'card': '5061 0606 0606 0606',
            'description': 'Success Test Card',
            'status': 'success'
        },
        {
            'card': '5061 0606 0606 0614',
            'description': 'Failed Test Card',
            'status': 'failed'
        },
        {
            'card': '4084 0840 8408 4081',
            'description': 'Generic Test Card',
            'status': 'success'
        }
    ]
    
    context = {
        'order': order,
        'test_cards': test_cards,
        'public_key': settings.PAYSTACK_PUBLIC_KEY,
        'title': 'Complete Your Payment',
    }
    
    return render(request, 'payments/instructions.html', context)


# Optional: Direct JS integration view
@login_required
def get_payment_details(request, order_id):
    """
    API endpoint to get payment details for frontend JS integration
    Returns JSON with payment initialization data
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Create payment transaction
    payment = PaymentTransaction.objects.create(
        order=order,
        user=request.user,
        amount=order.total_amount,
        paystack_reference=PaymentTransaction.generate_reference(),
        ip_address=get_client_ip(request),
    )
    
    # Get payment initialization data for frontend
    data = {
        'reference': payment.paystack_reference,
        'amount': payment.amount_in_kobo,
        'email': order.customer_email,
        'public_key': settings.PAYSTACK_PUBLIC_KEY,
        'callback_url': request.build_absolute_uri(
            reverse('payments:verify_payment')
        ),
        'metadata': {
            'order_id': order.id,
            'payment_id': payment.id,
        }
    }
    
    return JsonResponse({'status': 'success', 'data': data})

@require_GET
@login_required
def verify_payment(request):
    """Verify payment after Paystack redirect"""
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, "No payment reference provided")
        return redirect('cart:view_cart')
    
    try:
        payment = PaymentTransaction.objects.get(
            paystack_reference=reference,
            user=request.user
        )
        order = payment.order
        
        # Check if webhook already marked as successful
        if payment.status == 'success':
            # Webhook already processed it
            messages.success(request, "Payment already confirmed!")
            return redirect('payments:payment_success', order_id=order.id)
        
        # If not processed by webhook yet, verify manually
        paystack_service = PaystackService()
        verification = paystack_service.verify_transaction(reference)
        
        if verification.get('status') and verification['data']['status'] == 'success':
            # Update payment
            payment.status = 'success'
            payment.verified_at = datetime.now()
            payment.save()
            
            # Update order
            order.payment_status = 'success'
            order.save()
            
            # Clear cart
            from cart.models import Cart
            try:
                cart = Cart.objects.get(user=request.user)
                cart.items.all().delete()
            except Cart.DoesNotExist:
                pass
            
            # Send confirmation email
            from services.email_service import send_order_confirmation
            send_order_confirmation(request.user, order)
            
            messages.success(request, "Payment completed successfully!")
            return redirect('payments:payment_success', order_id=order.id)
        else:
            # Payment failed
            payment.status = 'failed'
            payment.save()
            
            order.payment_status = 'failed'
            order.save()
            
            error_msg = verification.get('message', 'Payment failed')
            messages.error(request, f"Payment Failed: {error_msg}")
            return redirect('payments:payment_failed', order_id=order.id)
            
    except PaymentTransaction.DoesNotExist:
        messages.error(request, "Payment transaction not found")
        return redirect('cart:view_cart')

@login_required
def payment_success(request, order_id):
    """Payment success page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Get the latest transaction for this order
    try:
        transaction = PaymentTransaction.objects.filter(
            order=order, 
            status='success'
        ).latest('created_at')
    except PaymentTransaction.DoesNotExist:
        transaction = None
    
    context = {
        'order': order,
        'transaction': transaction,
        'title': 'Payment Successful',
        'now': datetime.now(),
    }
    return render(request, 'payments/success.html', context)

@login_required
def payment_failed(request, order_id):
    """Payment failed page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Get the latest failed transaction
    try:
        transaction = PaymentTransaction.objects.filter(
            order=order, 
            status='failed'
        ).latest('created_at')
    except PaymentTransaction.DoesNotExist:
        transaction = None
    
    context = {
        'order': order,
        'transaction': transaction,
        'title': 'Payment Failed',
    }
    return render(request, 'payments/payment_failed.html', context)

# payments/views.py

@csrf_exempt
@require_POST
def webhook_view(request):
    """
    Paystack Webhook Handler
    Paystack sends POST requests here for instant notifications
    """
    # Get the Paystack signature for security verification
    signature = request.headers.get('x-paystack-signature', '')
    
    # Verify the webhook is from Paystack (CRITICAL FOR SECURITY)
    if not verify_paystack_signature(request.body, signature):
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    try:
        payload = json.loads(request.body.decode('utf-8'))
        event = payload.get('event')
        data = payload.get('data', {})
        
        print(f"📢 Webhook received: {event}")
        
        # Handle different events
        if event == 'charge.success':
            return handle_successful_charge(data)
        elif event == 'charge.failed':
            return handle_failed_charge(data)
        elif event == 'transfer.success':
            return handle_transfer_success(data)
        else:
            print(f"ℹ️ Unhandled event: {event}")
            return JsonResponse({'status': 'ignored'})
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def verify_paystack_signature(payload, signature):
    """
    Verify that the webhook is actually from Paystack
    This prevents fake webhooks from malicious actors
    """
    secret_key = settings.PAYSTACK_SECRET_KEY
    
    # Create HMAC signature with your secret key
    computed_signature = hmac.new(
        secret_key.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(computed_signature, signature)


def handle_successful_charge(data):
    """Handle successful payment webhook"""
    reference = data.get('reference')
    
    try:
        # Find the payment transaction
        payment = PaymentTransaction.objects.get(paystack_reference=reference)
        
        # Update payment
        payment.status = 'success'
        payment.verified_at = datetime.now()
        payment.metadata['webhook_data'] = data  # Store full response
        payment.save()
        
        # Update order
        order = payment.order
        order.payment_status = 'success'
        order.paystack_reference = reference
        
        # Mark email as not sent yet (will be sent by verify view or here)
        order.payment_email_sent = False
        order.save()
        
        # Send confirmation email (optional - can also do in verify view)
        from services.email_service import send_order_confirmation
        send_order_confirmation(order.user, order)
        
        print(f"✅ Webhook: Order {order.order_number} marked as paid")
        return JsonResponse({'status': 'success', 'order': order.order_number})
        
    except PaymentTransaction.DoesNotExist:
        print(f"⚠️ Webhook: Payment not found for reference {reference}")
        return JsonResponse({'error': 'Payment not found'}, status=404)


def handle_failed_charge(data):
    """Handle failed payment webhook"""
    reference = data.get('reference')
    
    try:
        payment = PaymentTransaction.objects.get(paystack_reference=reference)
        payment.status = 'failed'
        payment.save()
        
        order = payment.order
        order.payment_status = 'failed'
        order.save()
        
        print(f"❌ Webhook: Payment failed for {reference}")
        return JsonResponse({'status': 'notified'})
        
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({'error': 'Payment not found'}, status=404)

@require_GET
@login_required
def payment_status(request, order_number):
    """Check payment status for an order"""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    
    return JsonResponse({
        'order_number': order.order_number,
        'payment_status': order.payment_status
    })