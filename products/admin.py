from django.contrib import admin
from .models import Product, Review, ProductImage
from django.utils.html import format_html
import logging

logger = logging.getLogger(__name__)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'category',
        'price',
        'inventory_count',
        'is_active',
        'featured',
    ]

    list_filter = [
        'category',
        'is_active',
        'featured',
        'created_at',
    ]

    search_fields = ['name', 'description']

    prepopulated_fields = {
        'slug': ('name',),
    }

    readonly_fields = ['created_at', 'updated_at']

    # Main fieldset layout
    base_fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_price')
        }),
        ('Inventory', {
            'fields': ('category', 'inventory_count', 'is_active', 'featured')
        }),
        ('Variants', {
            'fields': ('available_sizes', 'available_colors')
        }),
        ('Fit Type (Cargo Jeans & Sweatpants)', {  # New section for fit type
            'fields': ('fit_type',),
            'classes': ('collapse',),
            'description': 'Choose Loose or Fit (only for Cargo Jeans & Sweatpants)',
        }),
        ('Detailed Measurements (Cargo Jeans & Sweatpants)', {
            'fields': (
                'waist_measurements',
                'hip_measurements',
                'length_measurements',
                'thigh_measurements',
                'rise_measurements',
            ),
            'classes': ('collapse',),
            'description': 'Only fill these for Cargo Jeans and Sweatpants.',
        }),
        ('Media', {
            'fields': ('image',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """
        Show fit_type + detailed measurements only for cargo jeans + sweatpants.
        """
        if obj is None:
            # Creating a new product → show all fields so category can be selected
            return self.base_fieldsets

        filtered = []
        for title, data in self.base_fieldsets:
            if title == 'Fit Type (Cargo Jeans & Sweatpants)' and obj.category not in ['cargo-jeans', 'sweatpants']:
                continue
            if title == 'Detailed Measurements (Cargo Jeans & Sweatpants)' and obj.category not in ['cargo-jeans', 'sweatpants']:
                continue
            filtered.append((title, data))
        return filtered


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'approved', 'created_at', 'approved_by',]
    list_filter = ['approved', 'rating', 'created_at']
    search_fields = ['user__username', 'comment']
    readonly_fields = ['created_at', 'approved_by']

    def save_model(self, request, obj, form, change):
        if obj.approved and not obj.approved_by:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)
        logger.info(f"Review {obj.id} saved by {request.user.username}")

# Inline admin for ProductImage
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1  # Number of empty forms to display
    fields = ['image', 'alt_text', 'is_main', 'image_preview']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: cover;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Preview'

# Register the ProductImage model separately (optional)
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image_preview', 'is_main', 'created_at']
    list_filter = ['is_main', 'created_at']
    list_editable = ['is_main']
    search_fields = ['product__name', 'alt_text']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Image'