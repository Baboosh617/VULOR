from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from cart.models import Cart, CartItem
from orders.forms import CheckoutForm
from orders.models import Order, OrderItem
from orders.shipping import get_shipping_info
from payments.models import PaymentTransaction
from services.email_service import send_order_confirmation
from services.inventory_service import reduce_inventory
from services.tasks import build_order_email_context
from vulor.testing import (
    StoreTestCase,
    make_order,
    make_product,
    make_transaction,
    make_user,
)


class OrderModelTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("orderuser")
        self.product = make_product(name="Order Product", price=Decimal("1500.00"), inventory_count=20)

    def test_order_number_generated_on_create(self):
        order = make_order(self.user)
        self.assertTrue(order.order_number)
        self.assertNotEqual(order.order_number, "")

    def test_default_status_and_payment_status(self):
        order = make_order(self.user)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.payment_status, "pending")

    def test_grand_total_includes_shipping(self):
        order = make_order(self.user, total_amount=Decimal("3000.00"), shipping_fee=Decimal("500.00"))
        self.assertEqual(order.grand_total, Decimal("3500.00"))

    def test_order_item_total_price(self):
        order = make_order(self.user)
        item = OrderItem.objects.create(
            order=order, product=self.product, quantity=2, price=Decimal("1500.00")
        )
        self.assertEqual(item.get_total_price(), Decimal("3000.00"))

    def test_order_total_items(self):
        order = make_order(self.user)
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
            "order_notes": "",
        }
        data.update(overrides)
        return data

    def test_valid_data(self):
        form = CheckoutForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_notes_are_optional(self):
        form = CheckoutForm(data=self._data(order_notes=""))
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


class CheckoutViewTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("buyer")
        self.product = make_product(name="Checkout Hoodie", price=Decimal("2000.00"), inventory_count=5)
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
            "order_notes": "Call before delivery",
        }
        data.update(overrides)
        return self.client.post(reverse("orders:checkout"), data)

    def test_get_renders_checkout_page_without_errors(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delivery")
        self.assertContains(response, "shipping-zones")  # json_script data block
        self.assertEqual(len(list(response.context["messages"])), 0)

    def test_get_with_empty_cart_redirects(self):
        self.user.cart.items.all().delete()
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("view_cart"))

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
        self.assertEqual(order.shipping_fee, Decimal("3500.00"))  # West zone (Lagos)
        self.assertEqual(order.shipping_zone, "West")
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

    def test_checkout_rejects_cart_exceeding_available_stock(self):
        # setUp gives the product inventory_count=5; bump the cart item's
        # quantity above that.
        cart_item = self.user.cart.items.get(product=self.product)
        cart_item.quantity = 6
        cart_item.save(update_fields=["quantity"])

        response = self._post_checkout()

        self.assertRedirects(response, reverse("view_cart"))
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.inventory_count, 5)  # untouched


class CheckoutPageQueryTests(StoreTestCase):
    """Regression test for the checkout() prefetch: checkout.html reads
    item.product.* per cart line, so query count must stay flat as the
    number of distinct products in the cart grows, not scale with it."""

    def setUp(self):
        self.user = make_user("checkoutquery")
        Cart.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.products = [
            make_product(name=f"Checkout Product {i}", inventory_count=20) for i in range(3)
        ]

    def test_checkout_page_query_count_flat_regardless_of_distinct_products(self):
        CartItem.objects.create(cart=self.user.cart, product=self.products[0])
        # Warm process-level caches first, matching the order_history/detail
        # query-count tests above — otherwise the count is order-dependent
        # across the full suite.
        self.client.get(reverse("orders:checkout"))
        with CaptureQueriesContext(connection) as queries_one_item:
            self.client.get(reverse("orders:checkout"))

        CartItem.objects.create(cart=self.user.cart, product=self.products[1])
        CartItem.objects.create(cart=self.user.cart, product=self.products[2])
        with CaptureQueriesContext(connection) as queries_three_items:
            self.client.get(reverse("orders:checkout"))

        self.assertEqual(len(queries_one_item), len(queries_three_items))


class EmailTemplateTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("mailuser", first_name="Ada")
        self.order = make_order(self.user)
        self.context = build_order_email_context(self.user, self.order)

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

    def test_context_links_are_absolute(self):
        self.assertTrue(self.context["order_url"].startswith("http"))
        self.assertIn(f"/payments/transfer/{self.order.id}/", self.context["payment_url"])


class EmailDispatchTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("dispatchuser", first_name="Ada")
        self.order = make_order(self.user)
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
        order = make_order(self.user, total_amount=Decimal("1000.00"), shipping_fee=Decimal("0.00"))
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any(order.order_number in s for s in subjects))


class OrderPaymentTransitionTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("transuser")
        self.order = make_order(self.user, payment_status="pending_verification")
        self.txn = make_transaction(self.order, status="pending_verification")

    def test_confirm_payment_updates_order_and_transaction(self):
        self.order.confirm_payment()
        self.order.refresh_from_db()
        self.txn.refresh_from_db()
        self.assertEqual(self.order.payment_status, "success")
        self.assertEqual(self.txn.status, "success")
        self.assertIsNotNone(self.txn.verified_at)

    def test_reject_payment_updates_order_and_transaction(self):
        self.order.reject_payment()
        self.order.refresh_from_db()
        self.txn.refresh_from_db()
        self.assertEqual(self.order.payment_status, "failed")
        self.assertEqual(self.txn.status, "rejected")

    def test_reject_payment_emails_customer(self):
        mail.outbox.clear()
        self.order.reject_payment()
        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].to, [self.user.email])

    def test_confirm_payment_works_without_transaction(self):
        self.txn.delete()
        self.order.confirm_payment()
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "success")

    def test_submit_receipt_moves_order_to_pending_verification(self):
        order = make_order(self.user, payment_status="pending")
        txn = make_transaction(order)
        order.submit_receipt(txn)
        order.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(order.payment_status, "pending_verification")
        self.assertEqual(txn.status, "pending_verification")
        self.assertIsNotNone(txn.submitted_at)


class OrderPaymentConcurrencyTests(StoreTestCase):
    """Regression tests for the confirm_payment/reject_payment locking fix.
    Two independently loaded Order instances (each representing what a
    separate overlapping request would have fetched via get_object_or_404,
    both read before either commits) must not both perform the state
    transition — only one may reduce inventory / send the rejection email."""

    def setUp(self):
        self.user = make_user("concurrency_user")
        self.product = make_product(name="Race Hoodie", inventory_count=10)
        self.order = make_order(self.user, payment_status="pending_verification")
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=3, price=Decimal("1000.00")
        )
        self.txn = make_transaction(self.order, status="pending_verification")

    def test_concurrent_confirm_payment_reduces_inventory_only_once(self):
        order_view_a = Order.objects.get(pk=self.order.pk)
        order_view_b = Order.objects.get(pk=self.order.pk)

        order_view_a.confirm_payment()
        order_view_b.confirm_payment()

        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.inventory_count, 7)  # 10 - 3, not 10 - 6
        self.assertTrue(self.order.inventory_adjusted)
        self.assertEqual(self.order.payment_status, "success")

    def test_concurrent_reject_payment_sends_email_only_once(self):
        order_view_a = Order.objects.get(pk=self.order.pk)
        order_view_b = Order.objects.get(pk=self.order.pk)

        mail.outbox.clear()
        order_view_a.reject_payment()
        order_view_b.reject_payment()

        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertEqual(len(rejected), 1)

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "failed")


class InventoryFloorTests(StoreTestCase):
    """Regression tests for the reduce_inventory floor check: stock must
    never be driven negative, whether reduced directly or via the
    payment_success signal after a payment has already been confirmed."""

    def setUp(self):
        self.user = make_user("stockuser")
        self.product = make_product(name="Scarce Hoodie", inventory_count=2)
        self.order = make_order(self.user, payment_status="pending_verification")
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=5, price=Decimal("1000.00")
        )
        self.txn = make_transaction(self.order, status="pending_verification")

    def test_reduce_inventory_raises_instead_of_going_negative(self):
        with self.assertRaises(ValueError):
            reduce_inventory(self.order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.inventory_count, 2)  # untouched

    def test_confirm_payment_does_not_crash_on_insufficient_stock(self):
        # Payment confirmation must still succeed even though this order's
        # quantity (5) exceeds available stock (2) — the order needs manual
        # stock review, but the payment-confirmation flow itself must not
        # raise up through the view.
        self.order.confirm_payment()
        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.order.payment_status, "success")
        self.assertFalse(self.order.inventory_adjusted)  # left False as the review signal
        self.assertEqual(self.product.inventory_count, 2)  # never went negative


class OrderAdminActionTests(StoreTestCase):
    def setUp(self):
        self.admin = make_user("root", is_staff=True, is_superuser=True)
        self.user = make_user("admcust")
        self.order = make_order(self.user, payment_status="pending_verification")
        self.txn = make_transaction(self.order, status="pending_verification")
        self.client.force_login(self.admin)

    def test_confirm_action_marks_order_paid(self):
        self.client.post(
            reverse("admin:orders_order_changelist"),
            {"action": "mark_payment_confirmed", "_selected_action": [self.order.pk]},
        )
        self.order.refresh_from_db()
        self.txn.refresh_from_db()
        self.assertEqual(self.order.payment_status, "success")
        self.assertEqual(self.txn.status, "success")

    def test_reject_action_notifies_customer(self):
        mail.outbox.clear()
        self.client.post(
            reverse("admin:orders_order_changelist"),
            {"action": "mark_payment_rejected", "_selected_action": [self.order.pk]},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "failed")
        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertEqual(len(rejected), 1)


class AbandonStaleOrdersTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("staleuser")

    def _order(self, payment_status="pending", age_hours=0):
        order = make_order(self.user, payment_status=payment_status)
        if age_hours:
            Order.objects.filter(pk=order.pk).update(
                created_at=timezone.now() - timezone.timedelta(hours=age_hours)
            )
            order.refresh_from_db()
        return order

    def test_old_pending_order_is_abandoned_and_transaction_failed(self):
        order = self._order(age_hours=72)
        txn = make_transaction(order)
        call_command("abandon_stale_orders")
        order.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(order.payment_status, "abandoned")
        self.assertEqual(txn.status, "failed")

    def test_recent_pending_order_is_untouched(self):
        order = self._order(age_hours=1)
        call_command("abandon_stale_orders")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_pending_verification_order_is_untouched(self):
        order = self._order(payment_status="pending_verification", age_hours=72)
        call_command("abandon_stale_orders")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending_verification")

    def test_custom_hours_argument(self):
        order = self._order(age_hours=5)
        call_command("abandon_stale_orders", hours=4)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "abandoned")

    def test_abandonment_unblocks_checkout_guard(self):
        self._order(age_hours=72)
        call_command("abandon_stale_orders")
        self.assertFalse(
            Order.objects.filter(user=self.user, payment_status="pending").exists()
        )


class OrderSuccessViewTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("successuser")
        self.order = make_order(self.user, payment_status="success")
        self.client.force_login(self.user)

    def test_paid_order_redirects_to_tracking(self):
        # The legacy success URL now redirects to the single canonical result
        # screen (order_detail), which owns the confirmed celebration.
        response = self.client.get(
            reverse("orders:order_success", args=[self.order.order_number])
        )
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )
        # The celebration itself lives on the tracking page.
        self.assertContains(response.client.get(response.url), "Confirmed.")

    def test_unpaid_order_redirects_to_detail(self):
        self.order.payment_status = "pending"
        self.order.save(update_fields=["payment_status"])
        response = self.client.get(
            reverse("orders:order_success", args=[self.order.order_number])
        )
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )


class ShippingZoneTests(TestCase):
    def test_zone_fees(self):
        self.assertEqual(get_shipping_info("Kaduna"), ("Kaduna", Decimal("1500.00")))
        self.assertEqual(get_shipping_info("Kano"), ("North", Decimal("2500.00")))
        self.assertEqual(get_shipping_info("Lagos"), ("West", Decimal("3500.00")))
        self.assertEqual(get_shipping_info("Enugu"), ("East", Decimal("4000.00")))
        self.assertEqual(get_shipping_info("Rivers"), ("South-South", Decimal("4500.00")))

    def test_unknown_state_returns_none(self):
        self.assertIsNone(get_shipping_info("Atlantis"))

    def test_checkout_form_rejects_unknown_state(self):
        form = CheckoutForm(data={
            "full_name": "Ada Obi",
            "phone_number": "08012345678",
            "email": "ada@example.com",
            "address_line": "1 Market St",
            "state": "Atlantis",
            "city": "Nowhere",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("state", form.errors)

    def test_all_template_states_are_deliverable(self):
        # The checkout template now renders state options by iterating the
        # shipping_zones context (built from orders/shipping.py), so options
        # can no longer drift from the table by construction. Assert the
        # dynamic loop is present rather than scanning hardcoded options.
        with open("orders/templates/orders/checkout.html") as f:
            html = f.read()
        self.assertIn("{% for state, info in shipping_zones.items %}", html)
        self.assertIn('<option value="{{ state }}">', html)


class OrderHistoryAndDetailQueryTests(StoreTestCase):
    """Regression tests for the prefetch_related additions to order_history
    and order_detail: query count must stay flat as orders/items grow,
    not scale linearly with them (the N+1 these fixes eliminate)."""

    def setUp(self):
        self.user = make_user("historyuser")
        self.client.force_login(self.user)
        # Pre-create the cart so the cart_context processor (which runs on
        # every page, including this one) doesn't lazily create it on the
        # first of the two measured requests below — that would add a
        # one-time INSERT unrelated to what this test is isolating.
        Cart.objects.create(user=self.user)
        self.products = [
            make_product(name=f"History Product {i}", inventory_count=20) for i in range(3)
        ]

    def _make_order_with_items(self, item_count):
        order = make_order(self.user)
        for product in self.products[:item_count]:
            OrderItem.objects.create(
                order=order, product=product, quantity=1, price=Decimal("1000.00")
            )
        return order

    def test_order_history_query_count_flat_regardless_of_order_count(self):
        self._make_order_with_items(2)
        # Warm process-level caches (ContentType, permissions, session) so both
        # measured requests below run against the same warm state — otherwise
        # the count is order-dependent across the full suite.
        self.client.get(reverse("orders:order_history"))
        with CaptureQueriesContext(connection) as queries_one:
            self.client.get(reverse("orders:order_history"))

        self._make_order_with_items(2)
        self._make_order_with_items(2)
        with CaptureQueriesContext(connection) as queries_three:
            self.client.get(reverse("orders:order_history"))

        self.assertEqual(len(queries_one), len(queries_three))

    def test_order_detail_query_count_flat_regardless_of_item_count(self):
        order_small = self._make_order_with_items(1)
        # Warm process-level caches so both measured requests below run against
        # the same warm state (see history test above).
        self.client.get(reverse("orders:order_detail", args=[order_small.order_number]))
        with CaptureQueriesContext(connection) as queries_one_item:
            self.client.get(
                reverse("orders:order_detail", args=[order_small.order_number])
            )

        order_large = self._make_order_with_items(3)
        with CaptureQueriesContext(connection) as queries_three_items:
            self.client.get(
                reverse("orders:order_detail", args=[order_large.order_number])
            )

        self.assertEqual(len(queries_one_item), len(queries_three_items))
