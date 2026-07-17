from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from products.models import Product, Review, Category, ProductImage
from accounts.models import CustomUser
from vulor.testing import StoreTestCase, make_product


class ProductModelTests(StoreTestCase):
    def test_slug_is_auto_generated_from_name(self):
        product = make_product(name="Cool Hoodie")
        self.assertEqual(product.slug, "cool-hoodie")

    def test_duplicate_name_gets_unique_slug(self):
        first = make_product(name="Duplicate Name")
        second = make_product(name="Duplicate Name")
        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith("duplicate-name-"))

    def test_discount_percentage(self):
        product = make_product(price=1000, compare_price=2000)
        self.assertEqual(product.get_discount_percentage(), 50)

    def test_no_discount_when_compare_price_missing(self):
        product = make_product(price=1000)
        self.assertEqual(product.get_discount_percentage(), 0)

    def test_is_in_stock(self):
        self.assertTrue(make_product(inventory_count=5).is_in_stock())
        self.assertFalse(make_product(inventory_count=0).is_in_stock())

    def test_available_sizes_and_colors_lists(self):
        product = make_product(available_sizes="S,M,L", available_colors="Black,White")
        self.assertEqual(product.get_available_sizes_list(), ["S", "M", "L"])
        self.assertEqual(product.get_available_colors_list(), ["Black", "White"])

    def test_formatted_sizes_for_cargo_jeans_includes_inches(self):
        product = make_product(category="cargo-jeans", available_sizes="30,32")
        self.assertEqual(product.get_formatted_sizes(), ['30"', '32"'])

    def test_formatted_sizes_for_tops_are_plain(self):
        product = make_product(category="hoodies", available_sizes="S,M")
        self.assertEqual(product.get_formatted_sizes(), ["S", "M"])

    def test_inventory_count_cannot_go_negative_at_db_level(self):
        """DB-level backstop (product_inventory_count_non_negative) — even a
        direct .update() bypassing all application logic must be rejected."""
        product = make_product(inventory_count=2)
        with self.assertRaises(IntegrityError):
            Product.objects.filter(pk=product.pk).update(inventory_count=-1)


class ProductRatingTests(StoreTestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="reviewer@example.com", username="reviewer", password="strongpass123"
        )
        self.product = make_product()

    def _add_review(self, rating, approved=True):
        # There's a one-review-per-user-per-product unique constraint, so each
        # review a test stacks up needs its own reviewer.
        n = Review.objects.count()
        user = CustomUser.objects.create_user(
            email=f"reviewer{n}@example.com", username=f"reviewer{n}", password="strongpass123"
        )
        return Review.objects.create(
            user=user,
            product=self.product,
            rating=rating,
            comment="Nice",
            approved=approved,
        )

    def test_average_rating_ignores_unapproved(self):
        self._add_review(4, approved=True)
        self._add_review(2, approved=False)
        self.assertEqual(self.product.average_rating, 4.0)

    def test_average_rating_rounds_to_one_decimal(self):
        self._add_review(4, approved=True)
        self._add_review(5, approved=True)
        self.assertEqual(self.product.average_rating, 4.5)

    def test_average_rating_zero_when_no_approved(self):
        self.assertEqual(self.product.average_rating, 0)

    def test_total_reviews_counts_approved_only(self):
        self._add_review(5, approved=True)
        self._add_review(3, approved=False)
        self.assertEqual(self.product.total_reviews, 1)

    def test_one_review_per_user_per_product(self):
        Review.objects.create(
            user=self.user, product=self.product, rating=5, comment="Nice", approved=True
        )
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.user, product=self.product, rating=3, comment="Again"
            )


class CategoryAndImageTests(StoreTestCase):
    def test_category_str(self):
        category = Category.objects.create(name="Hoodies", slug="hoodies")
        self.assertEqual(str(category), "Hoodies")

    def test_only_one_main_image_per_product(self):
        product = make_product()
        ProductImage.objects.create(
            product=product, image=SimpleUploadedFile("a.jpg", b"x"), is_main=True
        )
        with self.assertRaises(IntegrityError):
            ProductImage.objects.create(
                product=product, image=SimpleUploadedFile("b.jpg", b"x"), is_main=True
            )


class SecurityHeadersTests(StoreTestCase):
    """CSP is deployed in Report-Only mode (see CONTENT_SECURITY_POLICY_REPORT_ONLY
    in settings) — it must report, and must not enforce, until a separate,
    deliberate change turns enforcement on."""

    def test_csp_report_only_header_present_and_enforcing_header_absent(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy-Report-Only", response)
        self.assertNotIn("Content-Security-Policy", response)

    def test_csp_report_only_policy_allows_known_external_sources(self):
        response = self.client.get("/")
        policy = response["Content-Security-Policy-Report-Only"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("https://fonts.googleapis.com", policy)  # base.html <link>
        self.assertIn("https://cdn.jsdelivr.net", policy)  # dashboard Chart.js
