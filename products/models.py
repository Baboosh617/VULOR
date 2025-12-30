from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings
from django.db.models import Avg
from django.contrib.auth import get_user_model

User = get_user_model()

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
    inventory_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    # image_alt = models.ImageField(upload_to='products/alt/', blank=True, null=True, verbose_name="Alternative Image")

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
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    @property
    def total_reviews(self):
        return self.reviews.count()

    
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
    
    @property
    def average_rating(self):
        reviews = self.reviews.filter(approved=True)
        if reviews.exists():
            return round(reviews.aggregate(Avg('rating'))['rating__avg'], 1)
        return 0

    
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
        null=True,
        blank=True
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], 
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_reviews'
    )
    
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_review'),
        ]
    
    def __str__(self):
        if self.product:
            return f"Review by {self.user.username} for {self.product.name} - {self.rating} stars"
        return f"Store Review by {self.user.username} - {self.rating} stars"
    
    def get_star_rating(self):
        return range(self.rating)
    
    def get_empty_stars(self):
        return range(5 - self.rating)


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name
    


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/images/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_main', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['product'], condition=models.Q(is_main=True), name='unique_main_image')
        ]