from django.shortcuts import render, redirect, get_object_or_404
from products.models import Product, Review
from orders.models import Order
from dashboard.forms import ProductForm  # Use the one from forms.py
from django.contrib.auth import get_user_model
from django import forms
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Sum
from django.contrib import messages

User = get_user_model()

def dashboard_home(request):
    # Orders stats
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    completed_orders = Order.objects.filter(status="completed").count()
    
    # Sales stats (last 7 days)
    today = now().date()
    last_week = today - timedelta(days=6)
    sales_last_week = (
        Order.objects.filter(created_at__date__range=[last_week, today], status="completed")
        .values('created_at__date')
        .annotate(total_sales=Sum('total_amount'))
        .order_by('created_at__date')
    )
    sales_labels = [str(s['created_at__date']) for s in sales_last_week]
    sales_data = [float(s['total_sales']) for s in sales_last_week]

    # Reviews stats
    pending_reviews = Review.objects.filter(approved=False).count()
    approved_reviews = Review.objects.filter(approved=True).count()

    # Products stats
    total_products = Product.objects.count()

    # Low stock products (threshold of 5)
    RESTOCK_THRESHOLD = 5
    low_stock_products = Product.objects.filter(inventory_count__lte=RESTOCK_THRESHOLD)
    
    # Weekly Sales Summary
    today = now().date()
    last_week = today - timedelta(days=6)
    
    weekly_sales = (
        Order.objects.filter(status="completed", created_at__date__range=[last_week, today])
        .aggregate(total_sales=Sum('total_amount'))
    )['total_sales'] or 0

    context = {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "sales_labels": sales_labels,
        "sales_data": sales_data,
        "pending_reviews": pending_reviews,
        "approved_reviews": approved_reviews,
        "total_products": total_products,
        "low_stock_products": low_stock_products.count(),
        "weekly_sales": weekly_sales,
    }
    
    return render(request, "dashboard/home.html", context)


def review_list(request):
    reviews = Review.objects.filter(approved=False).order_by("-created_at")
    return render(request, "dashboard/reviews.html", {"reviews": reviews})

def approve_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.approved = True
    review.save()
    messages.success(request, f"Review from {review.user.username} has been approved.")
    return redirect("dashboard:review_list")

def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    messages.success(request, "Review has been deleted.")
    return redirect("dashboard:review_list")

def order_list(request):
    orders = Order.objects.all().order_by("-created_at")

    # Search
    query = request.GET.get("q")
    if query:
        orders = orders.filter(user__username__icontains=query)

    # Filter by status
    status_filter = request.GET.get("status")
    if status_filter in ["pending", "completed"]:
        orders = orders.filter(status=status_filter)

    return render(request, "dashboard/orders.html", {"orders": orders, "query": query, "status_filter": status_filter})

def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Simple toggle example: pending → completed → pending
    if order.status == "pending":
        order.status = "completed"
        messages.success(request, f"Order #{order.id} marked as completed.")
    else:
        order.status = "pending"
        messages.success(request, f"Order #{order.id} marked as pending.")

    order.save()
    return redirect("dashboard:order_list")

# List products with search/filter
def product_list(request):
    products = Product.objects.all().order_by("-created_at")
    
    # Search
    query = request.GET.get("q")
    if query:
        products = products.filter(name__icontains=query)
    
    # Filter by category
    category_filter = request.GET.get("category")
    if category_filter in dict(Product.CATEGORY_CHOICES).keys():
        products = products.filter(category=category_filter)
    
    # Filter by active status
    active_filter = request.GET.get("active")
    if active_filter == "true":
        products = products.filter(is_active=True)
    elif active_filter == "false":
        products = products.filter(is_active=False)
    
    context = {
        "products": products, 
        "query": query,
        "category_filter": category_filter,
        "active_filter": active_filter,
        "category_choices": Product.CATEGORY_CHOICES,
    }
    return render(request, "dashboard/products.html", context)

# Add product
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" added successfully.')
            return redirect('dashboard:product_list')
        else:
            # Debug: print form errors
            print("Form errors:", form.errors)
    else:
        form = ProductForm()
    
    context = {
        'form': form, 
        'title': 'Add New Product', 
        'product': None
    }
    return render(request, 'dashboard/product_form.html', context)

def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" updated successfully.')
            return redirect('dashboard:product_list')
        else:
            print("Form errors:", form.errors)
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form, 
        'title': f'Edit {product.name}', 
        'product': product
    }
    return render(request, 'dashboard/product_form.html', context)

# Delete product
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product_name = product.name
    product.delete()
    messages.success(request, f'Product "{product_name}" deleted successfully.')
    return redirect("dashboard:product_list")

def customer_list(request):
    users = User.objects.filter(is_superuser=False).order_by("-date_joined")
    query = request.GET.get("q")
    if query:
        users = users.filter(username__icontains=query)
    return render(request, "dashboard/customers.html", {"users": users, "query": query})

# Edit user
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

def edit_customer(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user.username} updated successfully.")
            return redirect("dashboard:customer_list")
    else:
        form = CustomerForm(instance=user)
    
    return render(request, "dashboard/customer_form.html", {"form": form, "user": user})

def toggle_user_active(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, "Cannot modify superuser status.")
        return redirect("dashboard:customer_list")
    
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"User {user.username} has been {status}.")
    return redirect("dashboard:customer_list")