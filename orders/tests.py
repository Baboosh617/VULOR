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


from django.template.loader import render_to_string


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailTemplateTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="mail@example.com", username="mailuser",
            password="strongpass123", first_name="Ada",
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("3000.00"),
            shipping_fee=Decimal("500.00"),
            shipping_address="1 Market St",
            shipping_city="Ikeja",
            shipping_state="Lagos",
            customer_email="mail@example.com",
        )
        self.context = {
            "user": self.user,
            "order": self.order,
            "site_url": "https://vulor.test",
            "bank_name": "GTBank",
            "account_name": "VULOR Store",
            "account_number": "0123456789",
        }

    def test_confirmation_email_shows_bank_details_while_pending(self):
        html = render_to_string("emails/order_confirmation.html", self.context)
        self.assertIn("GTBank", html)
        self.assertIn("0123456789", html)
        self.assertIn(self.order.order_number, html)
        self.assertIn(f"/payments/transfer/{self.order.id}/", html)
        self.assertIn("3500.00", html)  # grand total, not subtotal

    def test_confirmation_email_hides_bank_details_once_paid(self):
        self.order.payment_status = "success"
        self.order.save(update_fields=["payment_status"])
        html = render_to_string("emails/order_confirmation.html", self.context)
        self.assertNotIn("Account Number", html)
        self.assertNotIn("0123456789", html)

    def test_payment_receipt_email_renders_grand_total(self):
        html = render_to_string("emails/payment_receipt.html", self.context)
        self.assertIn("3500.00", html)
        self.assertIn("Bank Transfer", html)
        self.assertIn(self.order.order_number, html)


from unittest.mock import patch

from django.core import mail

from services.email_service import send_order_confirmation


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    BANK_TRANSFER_BANK_NAME="GTBank",
    BANK_TRANSFER_ACCOUNT_NAME="VULOR Store",
    BANK_TRANSFER_ACCOUNT_NUMBER="0123456789",
)
class EmailDispatchTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="dispatch@example.com", username="dispatchuser",
            password="strongpass123", first_name="Ada",
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("3000.00"),
            shipping_fee=Decimal("500.00"),
            shipping_address="1 Market St",
            shipping_city="Ikeja",
            shipping_state="Lagos",
            customer_email="dispatch@example.com",
        )
        mail.outbox.clear()  # drop the signal-driven creation emails

    @override_settings(EMAIL_ASYNC_ENABLED=False)
    def test_sends_synchronously_by_default(self):
        send_order_confirmation(self.user, self.order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.order_number, mail.outbox[0].subject)
        self.assertIn("0123456789", mail.outbox[0].alternatives[0][0])

    @override_settings(EMAIL_ASYNC_ENABLED=True)
    def test_falls_back_to_sync_when_broker_unavailable(self):
        with patch(
            "services.email_service.send_html_email_task.delay",
            side_effect=ConnectionError("broker down"),
        ):
            send_order_confirmation(self.user, self.order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.order_number, mail.outbox[0].subject)

    @override_settings(EMAIL_ASYNC_ENABLED=True)
    def test_queues_via_celery_when_async_enabled(self):
        with patch(
            "services.email_service.send_html_email_task.delay"
        ) as mock_delay:
            send_order_confirmation(self.user, self.order)
        mock_delay.assert_called_once()
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_ASYNC_ENABLED=False)
    def test_order_creation_signal_delivers_confirmation(self):
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("1000.00"),
            shipping_address="2 Side St",
            shipping_city="Ikeja",
            shipping_state="Lagos",
            customer_email="dispatch@example.com",
        )
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any(order.order_number in s for s in subjects))
