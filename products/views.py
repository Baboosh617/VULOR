import json
import logging
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Product
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Review, StoreReview
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

from .cache_utils import get_products_cache_version

logger = logging.getLogger(__name__)

from django.shortcuts import render
from django.db.models import Avg
from django.core.cache import cache
from .models import Product, Review
from .forms import ReviewForm

def home(request):
    
    version = get_products_cache_version()
    cache_key = f'home_page_data_v{version}'

    context = cache.get(cache_key)

    if not context:
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

        
        new_arrivals = Product.objects.filter(is_active=True).order_by('-created_at')[:6]


        latest_product = Product.objects.filter(is_active=True).order_by('-created_at').first()


        store_reviews = Review.objects.filter(approved=True, product__isnull=True).order_by('-created_at')[:10]
        avg_rating = store_reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        total_reviews = Review.objects.filter(approved=True).count()

        context = {
            'hero_products': hero_products,
            'new_arrivals': new_arrivals,
            'latest_product': latest_product,
            'store_reviews': store_reviews,
            'avg_rating': round(avg_rating, 1),
            'total_reviews': total_reviews,
        }


        cache.set(cache_key, context, 60 * 10)


    context['review_form'] = ReviewForm()
    return render(request, 'index.html', context)


def product_list(request):
    category = request.GET.get('category')
    search = request.GET.get('search')
    sort = request.GET.get('sort', 'newest')
    page_number = request.GET.get('page', 1)

    version = get_products_cache_version()
    cache_key = f'product_list_v{version}_{category}_{search}_{sort}_page_{page_number}'
    context = cache.get(cache_key)

    if not context:
        products = Product.objects.filter(is_active=True)
        valid_categories = dict(Product.CATEGORY_CHOICES).keys()

        if category in valid_categories:
            products = products.filter(category=category)

        if search:
            products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))

        if sort == 'price_low':
            products = products.order_by('price')
        elif sort == 'price_high':
            products = products.order_by('-price')
        elif sort == 'name':
            products = products.order_by('name')
        else:
            products = products.order_by('-created_at')

        paginator = Paginator(products, 10)
        paged_products = paginator.get_page(page_number)

        context = {
            'products': paged_products,
            'categories': Product.CATEGORY_CHOICES,
            'current_category': category,
            'search_query': search,
            'sort_method': sort,
        }

        cache.set(cache_key, context, 60 * 10)

    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    cache_key = f'product_detail_{slug}'
    context = cache.get(cache_key)

    version = get_products_cache_version()
    cache_key = f'product_detail_v{version}_{slug}'
   

    if not context:
        product = get_object_or_404(Product, slug=slug, is_active=True)
        related_products = Product.objects.filter(category=product.category, is_active=True).exclude(id=product.id)[:4]
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

        
        cache.set(cache_key, context, 60 * 5)

    return render(request, 'products/product_detail.html', context)

@ratelimit(key='user_or_ip', rate='5/m', block=True)
@login_required
def add_product_review(request, product_id):
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

@login_required
def add_store_review(request):
    if request.method == "POST":
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()

        if not rating or not comment:
            messages.error(request, "Please provide both a rating and a comment.")
            return redirect("home")

        try:
            rating = int(rating)
        except (TypeError, ValueError):
            messages.error(request, "Invalid rating.")
            return redirect("home")

        if rating not in (1, 2, 3, 4, 5):
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect("home")

        StoreReview.objects.create(user=request.user, rating=rating, comment=comment)
        messages.success(request, "Thanks for your feedback!")
    return redirect("home")