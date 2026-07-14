from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from products.models import Product, Review, ProductImage
from orders.models import Order
from dashboard.forms import ProductForm
from django.contrib.auth import get_user_model
from django import forms
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Sum
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse

from products.cache_utils import bump_products_cache_version

import logging

logger = logging.getLogger(__name__)
User = get_user_model()


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

@staff_member_required
def review_list(request):
    reviews = Review.objects.filter(approved=False).order_by("-created_at")
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get("page")
    reviews = paginator.get_page(page_number)
    return render(request, "dashboard/reviews.html", {"reviews": reviews})


@staff_member_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    logger.info(f"Review {review.id} deleted by {request.user.username}")
    messages.success(request, "Review has been deleted.")
    return redirect("dashboard:review_list")


@staff_member_required
def order_list(request):
    orders = Order.objects.all().order_by("-created_at").prefetch_related("paymenttransaction_set")

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

    order.reject_payment()

    logger.info(f"Payment for order {order.order_number} rejected by {request.user.username}")
    messages.success(request, f"Payment for order {order.order_number} rejected. The customer can retry.")
    return redirect("dashboard:order_list")


@staff_member_required
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


@staff_member_required
def product_list(request):
    products = Product.objects.all().order_by("-created_at")

    query = request.GET.get("q")
    if query:
        products = products.filter(name__icontains=query)

    category_filter = request.GET.get("category")
    if category_filter in dict(Product.CATEGORY_CHOICES).keys():
        products = products.filter(category=category_filter)

    active_filter = request.GET.get("active")
    if active_filter == "true":
        products = products.filter(is_active=True)
    elif active_filter == "false":
        products = products.filter(is_active=False)

    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    context = {
        "products": products_page,
        "query": query,
        "category_filter": category_filter,
        "active_filter": active_filter,
        "category_choices": Product.CATEGORY_CHOICES,
    }
    return render(request, "dashboard/products.html", context)


@staff_member_required
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            _handle_alternate_images(request, product)
            bump_products_cache_version()
            messages.success(request, f'Product "{product.name}" added successfully.')
            logger.info(f'Product "{product.name}" added by {request.user.username}.')
            return redirect('dashboard:product_list')
    else:
        form = ProductForm()

    return render(request, 'dashboard/product_form.html', {
        'form': form,
        'title': 'Add New Product',
        'product': None
    })


@staff_member_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    alternate_images = ProductImage.objects.filter(product=product)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            _handle_alternate_images(request, product)
            bump_products_cache_version()
            messages.success(request, f'Product "{product.name}" updated successfully.')
            logger.info(f'Product "{product.name}" edited by {request.user.username}.')
            return redirect('dashboard:product_list')
    else:
        form = ProductForm(instance=product)

    return render(request, 'dashboard/product_form.html', {
        'form': form,
        'title': f'Edit {product.name}',
        'product': product,
        'alternate_images': alternate_images,
    })


def _handle_alternate_images(request, product):
    """Extract alternate image upload logic to avoid repetition."""
    if not request.FILES.get('alternate_images'):
        return

    files = request.FILES.getlist('alternate_images')
    alt_texts = request.POST.getlist('alternate_alt_text')
    is_main_index = request.POST.get('alternate_is_main')

    for i, image_file in enumerate(files):
        if not image_file:
            continue
        alt_text = alt_texts[i] if i < len(alt_texts) else ''
        is_main = str(i) == is_main_index
        if is_main:
            ProductImage.objects.filter(product=product).update(is_main=False)
        ProductImage.objects.create(
            product=product,
            image=image_file,
            alt_text=alt_text,
            is_main=is_main
        )


@staff_member_required
def delete_alternate_image(request, product_id, image_id):
    image = get_object_or_404(ProductImage, id=image_id)
    if image.product.id != int(product_id):
        messages.error(request, 'Image does not belong to this product.')
        return redirect('dashboard:product_list')
    image.delete()
    logger.info(f'Alternate image {image_id} deleted by {request.user.username}.')
    messages.success(request, 'Image deleted.')
    return redirect('dashboard:edit_product', product_id=product_id)


@staff_member_required
def set_main_alternate_image(request, product_id, image_id):
    product = get_object_or_404(Product, id=product_id)
    ProductImage.objects.filter(product=product).update(is_main=False)
    image = get_object_or_404(ProductImage, id=image_id)
    image.is_main = True
    image.save()
    logger.info(f'Image {image_id} set as main for product {product_id} by {request.user.username}.')
    messages.success(request, 'Main image updated.')
    return redirect('dashboard:edit_product', product_id=product_id)


@staff_member_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product_name = product.name
    product.delete()
    bump_products_cache_version()
    logger.info(f'Product "{product_name}" deleted by {request.user.username}.')
    messages.success(request, f'Product "{product_name}" deleted.')
    return redirect("dashboard:product_list")


@staff_member_required
def customer_list(request):
    users = User.objects.filter(is_superuser=False).order_by("-date_joined")
    query = request.GET.get("q")
    if query:
        users = users.filter(username__icontains=query)
    paginator = Paginator(users, 10)
    page_number = request.GET.get("page")
    users = paginator.get_page(page_number)
    return render(request, "dashboard/customers.html", {"users": users, "query": query})


class CustomerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'border rounded p-2 w-full'}),
            'email': forms.EmailInput(attrs={'class': 'border rounded p-2 w-full'}),
            'first_name': forms.TextInput(attrs={'class': 'border rounded p-2 w-full'}),
            'last_name': forms.TextInput(attrs={'class': 'border rounded p-2 w-full'}),
        }


@staff_member_required
def edit_customer(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            logger.info(f"User {user.username} updated by {request.user.username}.")
            messages.success(request, f"User {user.username} updated.")
            return redirect("dashboard:customer_list")
    else:
        form = CustomerForm(instance=user)
    return render(request, "dashboard/customer_form.html", {"form": form, "user": user})


@staff_member_required
def toggle_user_active(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, "Cannot modify superuser status.")
        return redirect("dashboard:customer_list")
    user.is_active = not user.is_active
    user.save()
    status = "activated" if user.is_active else "deactivated"
    logger.info(f"User {user.username} {status} by {request.user.username}.")
    messages.success(request, f"User {user.username} has been {status}.")
    return redirect("dashboard:customer_list")

@staff_member_required
def approve_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.approved = True
    review.approved_by = request.user
    review.save(update_fields=['approved', 'approved_by'])
    logger.info(f"Review {review.id} approved by {request.user.username}")
    return redirect("dashboard:review_list")