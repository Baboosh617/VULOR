from django.test import TestCase, override_settings
from decimal import Decimal
from orders.models import Order, OrderItem
from orders.forms import CheckoutForm
from products.models import Product
from accounts.models import CustomUser
from django.core.files.uploadedfile import SimpleUploadedFile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OrderModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="orderuser@example.com", username="orderuser", password="strongpass123"
        )
        self.product = Product.objects.create(
            name="Order Product",
            description="desc",
            price=Decimal("1500.00"),
            category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"),
            inventory_count=20,
        )

    def _make_order(self, **kwargs):
        data = {
            "user": self.user,
            "total_amount": Decimal("3000.00"),
            "shipping_address": "1 Market St",
            "shipping_city": "Lagos",
            "shipping_state": "Lagos",
            "customer_email": "orderuser@example.com",
        }
        data.update(kwargs)
        return Order.objects.create(**data)

    def test_order_number_generated_on_create(self):
        order = self._make_order()
        self.assertTrue(order.order_number)
        self.assertNotEqual(order.order_number, "")

    def test_default_status_and_payment_status(self):
        order = self._make_order()
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.payment_status, "pending")

    def test_grand_total_includes_shipping(self):
        order = self._make_order(shipping_fee=Decimal("500.00"))
        self.assertEqual(order.grand_total, Decimal("3500.00"))

    def test_order_item_total_price(self):
        order = self._make_order()
        item = OrderItem.objects.create(
            order=order, product=self.product, quantity=2, price=Decimal("1500.00")
        )
        self.assertEqual(item.get_total_price(), Decimal("3000.00"))

    def test_order_total_items(self):
        order = self._make_order()
        OrderItem.objects.create(
            order=order, product=self.product, quantity=2, price=Decimal("1500.00")
        )
        OrderItem.objects.create(
            order=order, product=self.product, quantity=3, price=Decimal("1500.00")
        )
        self.assertEqual(order.get_total_items(), 5)


class CheckoutFormTests(TestCase):
    def _data(self, **overrides):
        data = {
            "full_name": "Ada Obi",
            "phone_number": "08012345678",
            "email": "ada@example.com",
            "address_line": "1 Market St",
            "state": "Lagos",
            "city": "Ikeja",
            "shipping_zone": "West",
            "order_notes": "",
        }
        data.update(overrides)
        return data

    def test_valid_data(self):
        form = CheckoutForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_notes_and_zone_are_optional(self):
        form = CheckoutForm(data=self._data(order_notes="", shipping_zone=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_notes_are_kept(self):
        form = CheckoutForm(data=self._data(order_notes="Please call before delivery"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["order_notes"], "Please call before delivery")

    def test_rejects_non_digit_phone(self):
        form = CheckoutForm(data=self._data(phone_number="0801234abcd"))
        self.assertFalse(form.is_valid())
        self.assertIn("phone_number", form.errors)

    def test_rejects_short_phone(self):
        form = CheckoutForm(data=self._data(phone_number="080123"))
        self.assertFalse(form.is_valid())
        self.assertIn("phone_number", form.errors)

    def test_requires_delivery_fields(self):
        form = CheckoutForm(data=self._data(full_name="", address_line=""))
        self.assertFalse(form.is_valid())
        self.assertIn("full_name", form.errors)
        self.assertIn("address_line", form.errors)


import tempfile

from django.urls import reverse

from cart.models import Cart, CartItem

TEMP_MEDIA = tempfile.mkdtemp(prefix="vulor-test-media-")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=TEMP_MEDIA,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class CheckoutViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="buyer@example.com", username="buyer", password="strongpass123"
        )
        self.product = Product.objects.create(
            name="Checkout Hoodie",
            description="desc",
            price=Decimal("2000.00"),
            category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"),
            inventory_count=5,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.client.force_login(self.user)

    def _post_checkout(self, **overrides):
        data = {
            "full_name": "Ada Obi",
            "phone_number": "08012345678",
            "email": "buyer@example.com",
            "address_line": "1 Market St",
            "state": "Lagos",
            "city": "Ikeja",
            "shipping_zone": "West",
            "order_notes": "Call before delivery",
        }
        data.update(overrides)
        return self.client.post(reverse("orders:checkout"), data)

    def test_checkout_creates_order_and_redirects_to_transfer_page(self):
        response = self._post_checkout()

        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("payments:transfer_instructions", args=[order.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(order.payment_method, "bank_transfer")
        self.assertEqual(order.order_notes, "Call before delivery")
        self.assertEqual(order.total_amount, Decimal("4000.00"))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(self.user.cart.items.count(), 0)

    def test_checkout_rejects_invalid_phone(self):
        response = self._post_checkout(phone_number="123")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_checkout_blocks_second_pending_order(self):
        self._post_checkout()
        CartItem.objects.create(cart=self.user.cart, product=self.product, quantity=1)
        self._post_checkout()
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
