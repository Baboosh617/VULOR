from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
import logging

from products.models import Product, ProductImage
from products.cache_utils import bump_products_cache_version
from dashboard.forms import ProductForm

logger = logging.getLogger(__name__)


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
