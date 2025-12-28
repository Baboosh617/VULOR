from django.db import models
from django.contrib.auth import get_user_model
from products.models import Product
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


User = get_user_model()

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart ({self.user.username})"

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])

    SIZE_CHOICES = [('S','Small'),('M','Medium'),('L','Large')]
    COLOR_CHOICES = [('red','Red'),('blue','Blue'),('green','Green')]
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def total_price(self):
        return self.quantity * self.product.price
    
    class Meta:
        unique_together = ['cart', 'product', 'size', 'color']