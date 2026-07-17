from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
from django.db.models import Sum
from django.http import JsonResponse
from datetime import timedelta

from orders.models import Order
from products.models import Product, Review


@staff_member_required  # ← FIXED: was unprotected
def dashboard_home(request):
    if 'dashboard_last_seen' not in request.session:
        request.session['dashboard_last_seen'] = now().isoformat()

    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    completed_orders = Order.objects.filter(status="completed").count()

    today = now().date()
    last_week = today - timedelta(days=6)

    sales_last_week = (
        Order.objects.filter(
            created_at__date__range=[last_week, today],
            status="completed"
        )
        .values('created_at__date')
        .annotate(total_sales=Sum('total_amount'))
        .order_by('created_at__date')
    )
    sales_labels = [str(s['created_at__date']) for s in sales_last_week]
    sales_data = [float(s['total_sales']) for s in sales_last_week]

    # ── Reviews ──────────────────────────────────────────────────────
    pending_reviews_count = Review.objects.filter(approved=False).count()  # ← FIXED name
    approved_reviews = Review.objects.filter(approved=True).count()

    # ── Products ─────────────────────────────────────────────────────
    total_products = Product.objects.count()

    # Receipts awaiting a human check — the dashboard's operational heartbeat.
    awaiting_verification = Order.objects.filter(payment_status="pending_verification").count()

    RESTOCK_THRESHOLD = 5
    restock_needed = Product.objects.filter(inventory_count__lte=RESTOCK_THRESHOLD)  # ← FIXED: queryset
    low_stock_count = restock_needed.count()

    # ── Weekly Sales ─────────────────────────────────────────────────
    weekly_sales = (
        Order.objects.filter(
            status="completed",
            created_at__date__range=[last_week, today]
        ).aggregate(total_sales=Sum('total_amount'))
    )['total_sales'] or 0

    context = {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "sales_labels": sales_labels,
        "sales_data": sales_data,
        "pending_reviews": approved_reviews,
        "pending_reviews_count": pending_reviews_count,   # ← FIXED: correct name
        "total_products": total_products,
        "awaiting_verification": awaiting_verification,
        "restock_needed": restock_needed,                 # ← FIXED: pass queryset
        "low_stock_products": low_stock_count,            # ← FIXED: count for badge
        "weekly_sales": weekly_sales,
    }

    return render(request, "dashboard/home.html", context)


@staff_member_required
def new_orders_check(request):
    last_seen_raw = request.session.get('dashboard_last_seen')
    last_seen = parse_datetime(last_seen_raw) if last_seen_raw else None
    new_count = Order.objects.filter(created_at__gt=last_seen).count() if last_seen else 0
    return JsonResponse({'new_orders': new_count})


@staff_member_required
def new_orders_ack(request):
    request.session['dashboard_last_seen'] = now().isoformat()
    return JsonResponse({'status': 'ok'})
