from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Sum, F
from django.utils.timezone import now, timedelta
from orders.models import Order, OrderItem
from products.models import Product
from django.http import HttpResponse

def send_weekly_sales_report():
    start_date = now() - timedelta(days=7)

    # Weekly orders
    orders = OrderItem.objects.filter(order__created_at__gte=start_date)


    # Revenue + total orders
    total_revenue = (
        OrderItem.objects.filter(order__created_at__gte=start_date)
        .aggregate(total=Sum(F("quantity") * F("price")))
        .get("total") or 0
    )    
    total_orders = orders.count()

    # Low stock products
    low_stock_products = Product.objects.filter(inventory_count__lte=5)

    # Weekly product sales breakdown
    product_sales = (
        OrderItem.objects.filter(order__created_at__gte=start_date)
        .values(
            product_name=F("product__name"),
            # product_id=F("product__id")
        )
        .annotate(
            total_quantity=Sum("quantity"),
            total_revenue=Sum(F("quantity") * F("price"))
        )
        .order_by("-total_quantity")
    )

    context = {
        "orders": orders,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "low_stock_products": low_stock_products,
        "product_sales": product_sales,
    }

    html_body = render_to_string("admin/emails/weekly_sales_report.html", context)
    text_body = render_to_string("admin/emails/weekly_sales_report_plain.txt", context)

    msg = EmailMultiAlternatives(
        subject="VULOR — Weekly Sales Report",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.ADMIN_EMAIL],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()

def test_weekly_report(request):
    send_weekly_sales_report()
    return HttpResponse("Weekly sales report sent!")