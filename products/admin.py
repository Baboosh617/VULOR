from django.contrib import admin
from .models import Product, Review

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
        ('Fit Type (Cargo Jeans Only)', {  # New section for fit type
            'fields': ('fit_type',),
            'classes': ('collapse',),
            'description': 'Choose Loose or Fit (only for Cargo Jeans)',
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
            if title == 'Fit Type (Cargo Jeans Only)' and obj.category != 'cargo-jeans':
                continue
            if title == 'Detailed Measurements (Cargo Jeans & Sweatpants)' and obj.category not in ['cargo-jeans', 'sweatpants']:
                continue
            filtered.append((title, data))
        return filtered


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'approved', 'created_at']
    list_filter = ['approved', 'rating', 'created_at']
    search_fields = ['user__username', 'comment']
    readonly_fields = ['created_at']
