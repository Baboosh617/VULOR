from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Product
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import Review
from .forms import ReviewForm
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Avg

def home(request):
    print(f"Current URL: {request.path}")
    print(f"Method: {request.method}")
    
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
    
    # ===== GET LATEST PRODUCT FROM EACH CATEGORY FOR MOBILE CAROUSEL =====
    # Define your categories (match with your Product model categories)
    categories = [
        'cargo-jeans',
        'sweatpants', 
        't-shirts',
        'shorts',
        'hoodies'
    ]
    
    # Get the latest active product from each category
    # Get latest product per category for mobile hero
    hero_products = []
    for category, _ in Product.CATEGORY_CHOICES:
        product = (
            Product.objects
            .filter(is_active=True, category=category)
            .order_by('-created_at')
            .first()
        )
        if product and product.image:
            hero_products.append(product)

    
    # ===== EXISTING CODE =====
    # Define all variables first (before any redirects)
    new_arrivals = Product.objects.order_by('-created_at')[:6]
    reviews = Review.objects.filter(approved=True)[:4]
    form = ReviewForm()
    
    store_reviews = Review.objects.filter(
        approved=True,
        product__isnull=True
    ).order_by('-created_at')[:10]
    
    avg_rating = store_reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    total_reviews = Review.objects.filter(approved=True).count()
    recent_products = Product.objects.filter(is_active=True).order_by('-created_at')[:5]
    
    # Handle POST requests after variables are defined
    if request.method == 'POST':
        if 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to submit a review.')
                return redirect('login')
            
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.save()
                messages.success(request, 'Thank you for your review! It will be visible after approval.')
                return redirect('home')
    
    # Build context with guaranteed defined variables
    context = {
        'store_reviews': store_reviews,
        'avg_rating': round(avg_rating, 1) if avg_rating else None,
        'total_reviews': total_reviews,
        'recent_products': recent_products,
        'reviews': reviews,
        'review_form': form,
        'latest_product': Product.objects.filter(is_active=True).order_by('-created_at').first(),
        'new_arrivals': Product.objects.filter(is_active=True).order_by('-created_at')[:6],
        'store_reviews': Review.objects.filter(approved=True).order_by('-created_at')[:10],
        # Add the hero_products for mobile carousel
        'hero_products': hero_products,
    }
    return render(request, 'index.html', context)

def product_list(request):
    products = Product.objects.filter(is_active=True)
    
    # Filtering
    category = request.GET.get('category')
    search = request.GET.get('search')
    sort = request.GET.get('sort', 'newest')
    
    if category:
        products = products.filter(category=category)
    
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Sorting
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'name':
        products = products.order_by('name')
    else:  # newest
        products = products.order_by('-created_at')
    
    categories = Product.CATEGORY_CHOICES
    
    context = {
        'products': products,
        'categories': categories,
        'current_category': category,
        'search_query': search,
        'sort_method': sort,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related_products = Product.objects.filter(
        category=product.category, 
        is_active=True
    ).exclude(id=product.id)[:4]
    
    context = {
        'product': product,
        'related_products': related_products,
        'sizes': product.get_available_sizes_list(),
        'colors': product.get_available_colors_list(),
        'FIT_CHOICES': Product.FIT_CHOICES,
    }
    return render(request, 'products/product_detail.html', context)


def submit_review(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to submit a review.')
            return redirect('login')
        
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            
            # Get the product if it exists
            product_id = request.POST.get('product_id')
            if product_id:
                try:
                    product = Product.objects.get(id=product_id)
                    review.product = product
                except Product.DoesNotExist:
                    pass  # Leave as store review if product not found
            
            review.save()
            messages.success(request, 'Thank you for your review! It will be visible after approval.')
    
    return redirect('home')


def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        if rating and comment:
            # Check if user already reviewed this product
            existing_review = Review.objects.filter(product=product, user=request.user).first()
            
            if existing_review:
                # Update existing review
                existing_review.rating = rating
                existing_review.comment = comment
                existing_review.save()
                messages.success(request, 'Your review has been updated!')
            else:
                # Create new review
                Review.objects.create(
                    product=product,
                    user=request.user,
                    rating=rating,
                    comment=comment
                )
                messages.success(request, 'Thank you for your review!')
        else:
            messages.error(request, 'Please provide both rating and comment.')
        
        return redirect('product_detail', slug=product.slug)
    
    # If not POST, redirect to product detail
    return redirect('product_detail', slug=product.slug)