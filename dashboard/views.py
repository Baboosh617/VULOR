from django.shortcuts import render, redirect, get_object_or_404
from products.models import Product, Review, ProductImage
from orders.models import Order
from dashboard.forms import ProductForm, ProductImageForm  
from django.contrib.auth import get_user_model
from django import forms
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Sum
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def dashboard_home(request):
    # Orders stats
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    completed_orders = Order.objects.filter(status="completed").count()
    
    # Sales stats
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

    # Low stock products stats (Check the stitistacs big man)
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

   

    paginator = Paginator(reviews, 10)
    page_number = request.GET.get("page")
    reviews = paginator.get_page(page_number)

    return render(request, "dashboard/reviews.html", {"reviews": reviews})

@staff_member_required
def approve_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    if not request.user.is_staff:
        messages.error(request, "You are not authorized to view this page.")
        return redirect("dashboard:home")
    review.approved = True
    review.save()
    logger.info(f"Review {review.id} approved by {request.user.username}")
    messages.success(request, f"Review from {review.user.username} has been approved.")
    return redirect("dashboard:review_list")

@staff_member_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    logger.info(f"Review {review.id} deleted by {request.user.username}")
    messages.success(request, "Review has been deleted.")
    return redirect("dashboard:review_list")

def order_list(request):
    orders = Order.objects.all().order_by("-created_at")

    
    query = request.GET.get("q")
    if query:
        orders = orders.filter(user__username__icontains=query)

    
    status_filter = request.GET.get("status")
    if status_filter in ["pending", "completed"]:
        orders = orders.filter(status=status_filter)

    return render(request, "dashboard/orders.html", {"orders": orders, "query": query, "status_filter": status_filter})

@staff_member_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    
    if order.status == "pending":
        order.status = "completed"
        messages.success(request, f"Order #{order.id} marked as completed.")
    else:
        order.status = "pending"
        messages.success(request, f"Order #{order.id} marked as pending.")

    logger.info(f"Order {order.id} status updated to {order.status} by {request.user.username}")
    order.save()
    return redirect("dashboard:order_list")


def product_list(request):
    products = Product.objects.all().order_by("-created_at")
    
    
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
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)
    return render(request, "dashboard/products.html", context)


@staff_member_required
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        
        if form.is_valid():
            product = form.save()
            
            # Handle alternate image upload
            if request.FILES.get('alternate_images'):
                # Handle multiple file uploads
                files = request.FILES.getlist('alternate_images')
                alt_texts = request.POST.getlist('alternate_alt_text')
                is_main_index = request.POST.get('alternate_is_main')
                
                for i, image_file in enumerate(files):
                    if image_file:  # Check if file was actually uploaded
                        alt_text = alt_texts[i] if i < len(alt_texts) else ''
                        is_main = str(i) == is_main_index
                        
                        # If setting as main, update all other images
                        if is_main:
                            ProductImage.objects.filter(product=product).update(is_main=False)
                        
                        # Create ProductImage instance
                        ProductImage.objects.create(
                            product=product,
                            image=image_file,
                            alt_text=alt_text,
                            is_main=is_main
                        )
            
            messages.success(request, f'Product "{product.name}" added successfully.')
            logger.info(f'Product "{product.name}" added by {request.user.username}.')
            return redirect('dashboard:product_list')
        else:
            # Debug
            print("Form errors:", form.errors)
    else:
        form = ProductForm()
    
    context = {
        'form': form, 
        'title': 'Add New Product', 
        'product': None
    }
    logger.info(f"User {request.user.username} accessed add product page.")
    return render(request, 'dashboard/product_form.html', context)

@staff_member_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    alternate_images = ProductImage.objects.filter(product=product)
    
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        
        if form.is_valid():
            product = form.save()
            
            # Handle alternate image upload
            if request.FILES.get('alternate_images'):
                # Handle multiple file uploads
                files = request.FILES.getlist('alternate_images')
                alt_texts = request.POST.getlist('alternate_alt_text')
                is_main_index = request.POST.get('alternate_is_main')
                
                for i, image_file in enumerate(files):
                    if image_file:  
                        alt_text = alt_texts[i] if i < len(alt_texts) else ''
                        is_main = str(i) == is_main_index
                        
                        # If setting as main, update all other images
                        if is_main:
                            ProductImage.objects.filter(product=product).update(is_main=False)
                        
                        
                        ProductImage.objects.create(
                            product=product,
                            image=image_file,
                            alt_text=alt_text,
                            is_main=is_main
                        )
            logger.info(f'Product "{product.name}" edited by {request.user.username}.')
            messages.success(request, f'Product "{product.name}" updated successfully.')
            return redirect('dashboard:product_list')
        else:
            print("Form errors:", form.errors)
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form, 
        'title': f'Edit {product.name}', 
        'product': product,
        'alternate_images': alternate_images,
    }
    return render(request, 'dashboard/product_form.html', context)

@staff_member_required
def delete_alternate_image(request, product_id, image_id):
    """Delete an alternate product image"""
    image = get_object_or_404(ProductImage, id=image_id)
    
    
    if image.product.id != int(product_id):
        messages.error(request, 'Image does not belong to the specified product.')
        return redirect('dashboard:product_list')
    
    image.delete()
    logger.info(f'Alternate image {image_id} for product {product_id} deleted by {request.user.username}.')
    messages.success(request, 'Alternate image deleted successfully.')
    return redirect('dashboard:edit_product', product_id=product_id)

def set_main_alternate_image(request, product_id, image_id):
    """Set an alternate image as the main product image"""
    product = get_object_or_404(Product, id=product_id)
    
   
    ProductImage.objects.filter(product=product).update(is_main=False)
    
   
    image = get_object_or_404(ProductImage, id=image_id)
    image.is_main = True
    image.save()
    logger.info(f'Alternate image {image_id} for product {product_id} set as main by {request.user.username}.')
    messages.success(request, 'Alternate image set as main.')
    return redirect('dashboard:edit_product', product_id=product_id)



@staff_member_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product_name = product.name
    product.delete()
    logger.info(f'Product "{product_name}" deleted by {request.user.username}.')
    messages.success(request, f'Product "{product_name}" deleted successfully.')
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
            messages.success(request, f"User {user.username} updated successfully.")
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
    logger.info(f"User {user.username} has been {status} by {request.user.username}.")
    messages.success(request, f"User {user.username} has been {status}.")
    return redirect("dashboard:customer_list")