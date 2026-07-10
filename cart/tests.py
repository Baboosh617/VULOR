from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from cart.models import Cart, CartItem
from products.models import Product
from accounts.models import CustomUser


class CartModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="cartuser@example.com", username="cartuser", password="strongpass123"
        )
        self.cart = Cart.objects.create(user=self.user)
        self.product = Product.objects.create(
            name="Cart Product",
            description="desc",
            price=500,
            category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"),
            inventory_count=20,
        )

    def test_cart_item_total_price(self):
        item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=3)
        self.assertEqual(item.total_price, 1500)

    def test_cart_total_items_and_price(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=4)
        self.assertEqual(self.cart.total_items, 6)
        self.assertEqual(self.cart.total_price, 3000)

    def test_unique_cart_product_size_color(self):
        CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, size="M", color="Black"
        )
        with self.assertRaises(IntegrityError):
            CartItem.objects.create(
                cart=self.cart, product=self.product, quantity=1, size="M", color="Black"
            )


class CartViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="cartview@example.com", username="cartview", password="strongpass123"
        )
        self.product = Product.objects.create(
            name="View Product",
            description="desc",
            price=500,
            category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"),
            inventory_count=20,
        )

    def test_add_to_cart_requires_login(self):
        response = self.client.post(
            reverse("add_to_cart", args=[self.product.id]), {"quantity": 1}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_add_to_cart_creates_item_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("add_to_cart", args=[self.product.id]),
            {"quantity": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CartItem.objects.count(), 1)
        item = CartItem.objects.first()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.cart.user, self.user)
