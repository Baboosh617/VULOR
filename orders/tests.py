from django.test import TestCase, override_settings
from decimal import Decimal
from orders.models import Order, OrderItem
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

    def test_paystack_amount_includes_shipping(self):
        order = self._make_order(shipping_fee=Decimal("500.00"))
        self.assertEqual(order.paystack_amount, 350000)

    def test_grand_total_includes_shipping(self):
        order = self._make_order(shipping_fee=Decimal("500.00"))
        self.assertEqual(order.grand_total, Decimal("3500.00"))

    def test_order_item_total_price(self):
        order = self._make_order()
        item = OrderItem.objects.create(
            order=order, product=self.product, quantity=2, price=Decimal("1500.00")
        )
        self.assertEqual(item.get_total_price, Decimal("3000.00"))

    def test_order_total_items(self):
        order = self._make_order()
        OrderItem.objects.create(
            order=order, product=self.product, quantity=2, price=Decimal("1500.00")
        )
        OrderItem.objects.create(
            order=order, product=self.product, quantity=3, price=Decimal("1500.00")
        )
        self.assertEqual(order.get_total_items(), 5)
