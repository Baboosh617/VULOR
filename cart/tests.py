from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from cart.context_processors import cart_context
from cart.models import Cart, CartItem
from products.models import Product
from accounts.models import CustomUser
from vulor.testing import StoreTestCase


class CartModelTests(StoreTestCase):
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
        # Same product in two size variants = two distinct cart lines (the
        # (cart, product, size, color) unique constraint forbids identical rows).
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2, size="S")
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=4, size="M")
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


class CartContextProcessorTests(StoreTestCase):
    """cart_context runs on every page render for every logged-in user, so
    its query count matters more than almost anything else in the app.
    These tests lock in both correctness (same values as the Cart model
    properties) and the query count, so a future change can't silently
    reintroduce the N+1."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="ctxuser@example.com", username="ctxuser", password="strongpass123"
        )
        self.cart = Cart.objects.create(user=self.user)
        self.product_a = Product.objects.create(
            name="Context Hoodie A", description="desc", price=1000,
            category="hoodies", image=SimpleUploadedFile("a.jpg", b"x"), inventory_count=20,
        )
        self.product_b = Product.objects.create(
            name="Context Hoodie B", description="desc", price=750,
            category="hoodies", image=SimpleUploadedFile("b.jpg", b"x"), inventory_count=20,
        )
        CartItem.objects.create(cart=self.cart, product=self.product_a, quantity=2)  # 2000
        CartItem.objects.create(cart=self.cart, product=self.product_b, quantity=3)  # 2250

    def _request(self, user):
        from django.test import RequestFactory
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_totals_match_cart_model_properties(self):
        # Same values the (unchanged) Cart.total_items/total_price
        # properties would produce — this must not have changed.
        context = cart_context(self._request(self.user))
        self.assertEqual(context["cart_total_items"], self.cart.total_items)
        self.assertEqual(context["cart_total_price"], self.cart.total_price)
        self.assertEqual(context["cart_total_items"], 5)
        self.assertEqual(context["cart_total_price"], 4250)

    def test_anonymous_user_gets_zero_without_querying(self):
        from django.contrib.auth.models import AnonymousUser
        with CaptureQueriesContext(connection) as queries:
            context = cart_context(self._request(AnonymousUser()))
        self.assertEqual(context, {"cart_total_items": 0, "cart_total_price": 0})
        self.assertEqual(len(queries), 0)

    def test_query_count_does_not_scale_with_item_count(self):
        # Regression guard for the N+1 fix: previously this was 2 queries
        # (one per total_items/total_price property call) plus one more
        # per cart item for item.product.price. Fetching once with
        # prefetch_related('items__product') makes it constant regardless
        # of how many items are in the cart.
        with CaptureQueriesContext(connection) as queries:
            cart_context(self._request(self.user))
        query_count_two_items = len(queries)

        for i in range(5):
            product = Product.objects.create(
                name=f"Bulk Product {i}", description="desc", price=100,
                category="hoodies", image=SimpleUploadedFile(f"bulk{i}.jpg", b"x"),
                inventory_count=20,
            )
            CartItem.objects.create(cart=self.cart, product=product, quantity=1)

        with CaptureQueriesContext(connection) as queries:
            cart_context(self._request(self.user))
        query_count_seven_items = len(queries)

        self.assertEqual(query_count_two_items, query_count_seven_items)


class CartViewTests(StoreTestCase):
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


class CartPageQueryTests(StoreTestCase):
    """Regression test for the view_cart prefetch: cart.html reads
    item.product.* per row, so query count must stay flat as the number of
    distinct products in the cart grows, not scale with it."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="cartquery@example.com", username="cartquery", password="strongpass123"
        )
        self.client.force_login(self.user)
        self.cart = Cart.objects.create(user=self.user)

    def _make_product(self, name):
        return Product.objects.create(
            name=name, description="desc", price=500, category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"), inventory_count=20,
        )

    def test_cart_page_query_count_flat_regardless_of_distinct_products(self):
        CartItem.objects.create(cart=self.cart, product=self._make_product("Solo Item"))
        with CaptureQueriesContext(connection) as queries_one_item:
            self.client.get(reverse("view_cart"))

        CartItem.objects.create(cart=self.cart, product=self._make_product("Second Item"))
        CartItem.objects.create(cart=self.cart, product=self._make_product("Third Item"))
        with CaptureQueriesContext(connection) as queries_three_items:
            self.client.get(reverse("view_cart"))

        self.assertEqual(len(queries_one_item), len(queries_three_items))
