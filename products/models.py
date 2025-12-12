from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('hoodies', 'Hoodies'),
        ('tee-shirts', 'Tee Shirts'),
        ('cargo-jeans', 'Cargo Jeans'),
        ('sweatpants', 'Sweatpants'),
        ('tank-tops', 'Tank Tops'),
    ]
    
    SIZE_CHOICES = [
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', '2X Large'),
    ]
    
    NUMERIC_SIZE_CHOICES = [
        ('28', '28'),
        ('30', '30'),
        ('32', '32'),
        ('34', '34'),
        ('36', '36'),
        ('38', '38'),
        ('40', '40'),
        ('42', '42'),
    ]

    # New: Fit type for cargos
    FIT_CHOICES = [
        ('loose', 'Loose'),
        ('fit', 'Fit'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    image = models.ImageField(upload_to='products/')
    featured = models.BooleanField(default=False)
    inventory_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # ✅ Low stock tracking
    low_stock_email_sent = models.BooleanField(default=False)
    
    available_sizes = models.CharField(max_length=100, default='S,M,L,XL')
    available_colors = models.CharField(max_length=200, default='Black,White')
    
    waist_measurements = models.TextField(blank=True, help_text="Waist measurements in inches (for cargo jeans and sweatpants)")
    hip_measurements = models.TextField(blank=True, help_text="Hip measurements in inches (for cargo jeans and sweatpants)")
    length_measurements = models.TextField(blank=True, help_text="Length measurements in inches (for cargo jeans and sweatpants)")
    thigh_measurements = models.TextField(blank=True, help_text="Thigh measurements in inches (for cargo jeans)")
    rise_measurements = models.TextField(blank=True, help_text="Rise measurements in inches (for cargo jeans)")

    # New field for cargo fit type
    fit_type = models.CharField(max_length=10, choices=FIT_CHOICES, blank=True, null=True, help_text="Only for cargo jeans")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    # def save(self, *args, **kwargs):
    #     if not self.slug:
    #         self.slug = slugify(self.name)
    #     super().save(*args, **kwargs)
    
    def get_discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0
    
    def is_in_stock(self):
        return self.inventory_count > 0
    
    def get_available_sizes_list(self):
        return [size.strip() for size in self.available_sizes.split(',')]
    
    def get_available_colors_list(self):
        return [color.strip() for color in self.available_colors.split(',')]
    
    def has_detailed_measurements(self):
        return self.category in ['cargo-jeans', 'sweatpants']

    def save(self, *args, **kwargs):
        # Generate base slug from name
        if self.name:
            base_slug = slugify(self.name)
        else:
            base_slug = "product"
        
        # If this is a new product OR slug is empty
        if not self.pk or not self.slug:
            # Find the next available number for this base slug
            existing_slugs = Product.objects.filter(slug__startswith=base_slug)
            
            if existing_slugs.exists():
                # Find the highest number after the base slug
                max_number = 0
                for existing_slug in existing_slugs.values_list('slug', flat=True):
                    # Check if slug is exactly base_slug (no number)
                    if existing_slug == base_slug:
                        max_number = max(max_number, 1)
                    # Check if slug has a number at the end (e.g., white-tee-1)
                    elif existing_slug.startswith(f"{base_slug}-"):
                        try:
                            # Extract the number after the dash
                            number_part = existing_slug.split(f"{base_slug}-")[-1]
                            if number_part.isdigit():
                                max_number = max(max_number, int(number_part))
                        except:
                            pass
                
                # If base slug exists or we found numbered slugs, add next number
                if Product.objects.filter(slug=base_slug).exists() or max_number > 0:
                    if max_number == 0:
                        # Base slug exists but no numbered ones yet
                        self.slug = f"{base_slug}-1"
                    else:
                        # Use the next available number
                        self.slug = f"{base_slug}-{max_number + 1}"
                else:
                    # No existing slugs with this base
                    self.slug = base_slug
            else:
                # No existing slugs at all
                self.slug = base_slug
        
        super().save(*args, **kwargs)
    
    def get_formatted_sizes(self):
        """Return sizes formatted for display based on category"""
        if not self.available_sizes:
            return []
        
        sizes = [s.strip() for s in self.available_sizes.split(',') if s.strip()]
        if self.category in ['cargo-jeans', 'sweatpants']:
            return [f"{size}\"" for size in sizes]
        else:
            return sizes
    
    def get_formatted_colors(self):
        """Return colors formatted for display"""
        if not self.available_colors:
            return []
        return [c.strip() for c in self.available_colors.split(',') if c.strip()]
    
    def get_measurements_dict(self):
        measurements = {}
        if self.waist_measurements:
            measurements['Waist'] = self.waist_measurements
        if self.hip_measurements:
            measurements['Hip'] = self.hip_measurements
        if self.length_measurements:
            measurements['Length'] = self.length_measurements
        if self.thigh_measurements:
            measurements['Thigh'] = self.thigh_measurements
        if self.rise_measurements:
            measurements['Rise'] = self.rise_measurements
        return measurements
class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(
        "products.Product", 
        on_delete=models.CASCADE, 
        related_name="reviews",
        null=True,      # Allows NULL in the database
        blank=True      # Allows blank in forms/admin
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], 
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        if self.product:
            return f"Review by {self.user.username} for {self.product.name} - {self.rating} stars"
        return f"Store Review by {self.user.username} - {self.rating} stars"
    
    def get_star_rating(self):
        return range(self.rating)
    
    def get_empty_stars(self):
        return range(5 - self.rating)
    
    # Helper method to check if it's a store review
    def is_store_review(self):
        return self.product is None

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name