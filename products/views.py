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

def home(request):

    print(f"Current URL: {request.path}")
    print(f"Method: {request.method}")
    
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
    new_arrivals = Product.objects.order_by('-created_at')[:6]
    
    # Get approved reviews (always show at least 4 if available)
    reviews = Review.objects.filter(approved=True)[:4]
    
    # Initialize form
    form = ReviewForm()

    if request.method == 'POST':
        # Check if this is a review submission
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
                # Redirect to home page to show the success message
                return redirect('home')
    
    context = {
        'new_arrivals': new_arrivals,
        'reviews': reviews,
        'review_form': form,
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
            review.save()
            messages.success(request, 'Thank you for your review! It will be visible after approval.')
    
    # Always redirect back to home
    return redirect('home')