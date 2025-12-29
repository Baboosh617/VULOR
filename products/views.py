import json
import logging
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Product
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Review
from .forms import ReviewForm
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.core.paginator import Paginator
from django.db import IntegrityError
from django_ratelimit.decorators import ratelimit
from django.views.decorators.cache import cache_page
from django.core.cache import cache

logger = logging.getLogger(__name__)

@cache_page(60 * 5)
def home(request):    
    # GET LATEST PRODUCT FROM EACH CATEGORY FOR MOBILE CAROUSEL
    
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
    
    # Build context with guaranteed defined variables
    context = {
        'store_reviews': store_reviews,
        'avg_rating': round(avg_rating, 1) if avg_rating else None,
        'total_reviews': total_reviews,
        'recent_products': recent_products,
        'reviews': reviews,
        'review_form': form,
        'latest_product': Product.objects.filter(is_active=True).order_by('-created_at').first(),
        'new_arrivals': new_arrivals,
        'store_reviews': store_reviews,
        # Add the hero_products for mobile carousel
        'hero_products': hero_products,
    }
    return render(request, 'index.html', context)

def product_list(request):
    cache_key = f"product_list_{request.GET.get('category')}_{request.GET.get('search')}_{request.GET.get('sort')}_{request.GET.get('page')}"
    products = cache.get(cache_key)
    
    if not products:
        products = Product.objects.filter(is_active=True)
        # ... apply filtering, sorting, pagination ...
        cache.set(cache_key, products, 60*5)  # cache 5 minutes
    
    # Filtering
    category = request.GET.get('category')
    search = request.GET.get('search')
    sort = request.GET.get('sort', 'newest')
    
    valid_categories = dict(Product.CATEGORY_CHOICES).keys()

    if category in valid_categories:
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

    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)
    
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

    reviews = product.reviews.filter(approved=True).select_related('user')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']

    
    context = {
        'product': product,
        'related_products': related_products,
        'sizes': product.get_available_sizes_list(),
        'colors': product.get_available_colors_list(),
        'FIT_CHOICES': Product.FIT_CHOICES,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1) if avg_rating else None,
    }
    return render(request, 'products/product_detail.html', context)

@ratelimit(key='user_or_ip', rate='5/m', block=True)
@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method != 'POST':
        return redirect('product_detail', slug=product.slug)

    rating = request.POST.get('rating')
    comment = request.POST.get('comment')

    if not rating or not comment:
        messages.error(request, 'Please provide both rating and comment.')
        return redirect('product_detail', slug=product.slug)
    
    existing_review = Review.objects.filter(
        product=product,
        user=request.user
    ).first()

    if existing_review:
        existing_review.rating = rating
        existing_review.comment = comment
        existing_review.save()
        messages.success(request, 'Your review has been updated!')
    else:
        try:
            Review.objects.create(
                product=product,
                user=request.user,
                rating=rating,
                comment=comment
            )
        except Exception as e:
            logger.error(f"Error adding review: {e}")
            messages.error(request, 'An error occurred while adding your review. Please try again later.')
            return redirect('product_detail', slug=product.slug)
        logger.info(f"User {request.user.username} added a review for {product.name}")
        messages.success(request, 'Thank you for your review!')

    return redirect('product_detail', slug=product.slug)
