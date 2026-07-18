import importlib
import io
from decimal import Decimal
from unittest.mock import patch

from PIL import Image

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from payments.forms import ReceiptUploadForm, RECEIPT_MAX_SIZE
from payments.models import PaymentTransaction
from vulor.testing import (
    StoreTestCase,
    make_order,
    make_product,
    make_test_image_bytes,
    make_transaction,
    make_user,
)


class PaymentTransactionTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("txuser")
        self.order = make_order(self.user, total_amount=Decimal("1000.00"), shipping_fee=Decimal("0.00"))

    def test_generate_reference_returns_unique_strings(self):
        ref1 = PaymentTransaction.generate_reference()
        ref2 = PaymentTransaction.generate_reference()
        self.assertIsInstance(ref1, str)
        self.assertNotEqual(ref1, ref2)

    def test_bank_transfer_fields_default_empty(self):
        tx = make_transaction(self.order, amount=Decimal("1200.00"))
        self.assertEqual(tx.status, "pending")
        self.assertFalse(tx.receipt)
        self.assertEqual(tx.transaction_reference, "")
        self.assertIsNone(tx.submitted_at)

    def test_latest_for_returns_newest_matching_transaction(self):
        make_transaction(self.order, status="failed")
        active = make_transaction(self.order)
        found = PaymentTransaction.objects.latest_for(self.order, ["pending"])
        self.assertEqual(found, active)
        self.assertIsNone(
            PaymentTransaction.objects.latest_for(self.order, ["pending_verification"])
        )


class ReceiptUploadFormTests(TestCase):
    def _form(self, filename="receipt.jpg", content=None, reference=""):
        if content is None:
            content = make_test_image_bytes()
        return ReceiptUploadForm(
            data={"transaction_reference": reference},
            files={"receipt": SimpleUploadedFile(filename, content)},
        )

    def test_valid_image_receipt(self):
        form = self._form("receipt.jpg")
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_pdf_with_reference(self):
        form = self._form(
            "receipt.pdf", content=b"%PDF-1.4 minimal", reference="TRF/2026/0001"
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["transaction_reference"], "TRF/2026/0001")

    def test_reference_is_optional(self):
        form = self._form("receipt.png")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["transaction_reference"], "")

    def test_rejects_disallowed_extension(self):
        form = self._form("receipt.exe")
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_rejects_oversized_file(self):
        form = self._form("receipt.jpg", content=b"x" * (RECEIPT_MAX_SIZE + 1))
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_receipt_is_required(self):
        form = ReceiptUploadForm(data={"transaction_reference": "abc"}, files={})
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_rejects_non_image_bytes_disguised_with_an_image_extension(self):
        """Regression test: content_type/extension are client-supplied and
        spoofable — a file that isn't actually a decodable image must be
        rejected even though its name/extension look legitimate."""
        form = self._form("receipt.jpg", content=b"this is not an image")
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_rejects_file_renamed_to_pdf_without_magic_bytes(self):
        # PDFs skip the Pillow check but must carry the %PDF- magic prefix —
        # an arbitrary file renamed .pdf is the cheapest way to smuggle
        # something the staff member is then required to open.
        form = self._form("receipt.pdf", content=b"MZ\x90 definitely not a pdf")
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_image_is_reencoded_to_jpeg(self):
        # Images are never stored as the customer's original bytes — they're
        # decoded and re-saved, so the stored file is always a fresh JPEG.
        form = self._form("receipt.png", content=make_test_image_bytes("PNG"))
        self.assertTrue(form.is_valid(), form.errors)
        cleaned = form.cleaned_data["receipt"]
        self.assertTrue(cleaned.name.endswith(".jpg"))
        self.assertEqual(Image.open(cleaned).format, "JPEG")

    def test_reencode_strips_exif_and_appended_payload(self):
        # A valid JPEG can still carry camera EXIF (GPS/device metadata that
        # staff would then download and email around) and appended bytes (an
        # image+archive polyglot). Neither may survive the re-encode.
        exif = Image.Exif()
        exif[0x0110] = "SpyPhone 3000"  # camera Model tag
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="JPEG", exif=exif)
        payload = b"PK\x03\x04-smuggled-archive-payload"

        form = self._form("receipt.jpg", content=buf.getvalue() + payload)
        self.assertTrue(form.is_valid(), form.errors)
        cleaned_bytes = form.cleaned_data["receipt"].read()
        self.assertNotIn(b"smuggled", cleaned_bytes)
        self.assertEqual(dict(Image.open(io.BytesIO(cleaned_bytes)).getexif()), {})

    def test_rejects_image_exceeding_pixel_cap(self):
        # The cap is enforced from the header-declared dimensions before any
        # full decode — a decompression bomb never gets decoded at all.
        buf = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buf, format="PNG")
        with patch("payments.forms.RECEIPT_MAX_PIXELS", 8):
            form = self._form("receipt.png", content=buf.getvalue())
            valid = form.is_valid()
        self.assertFalse(valid)
        self.assertIn("receipt", form.errors)


class BankTransferFlowTests(StoreTestCase):
    def setUp(self):
        self.user = make_user("flowuser")
        self.client.force_login(self.user)
        self.order = make_order(self.user)

    def _submit_receipt(self, filename="receipt.jpg", reference=""):
        return self.client.post(
            reverse("payments:submit_receipt", args=[self.order.id]),
            {
                "receipt": SimpleUploadedFile(filename, make_test_image_bytes()),
                "transaction_reference": reference,
            },
        )

    def test_instructions_page_shows_bank_details_and_creates_transaction(self):
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GTBank")
        self.assertContains(response, "0123456789")
        self.assertContains(response, self.order.order_number)
        txn = PaymentTransaction.objects.get(order=self.order)
        self.assertEqual(txn.status, "pending")
        self.assertEqual(txn.amount, Decimal("3500.00"))

    def test_instructions_page_reuses_existing_pending_transaction(self):
        url = reverse("payments:transfer_instructions", args=[self.order.id])
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(PaymentTransaction.objects.filter(order=self.order).count(), 1)

    @patch("services.email_service.ADMIN_EMAIL", "admin@vulor.test")
    def test_submit_receipt_marks_pending_verification_and_emails_admin(self):
        response = self._submit_receipt(reference="TRF-001")
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending_verification")

        txn = PaymentTransaction.objects.get(order=self.order)
        self.assertEqual(txn.status, "pending_verification")
        self.assertTrue(txn.receipt)
        self.assertEqual(txn.transaction_reference, "TRF-001")
        self.assertIsNotNone(txn.submitted_at)

        admin_emails = [m for m in mail.outbox if "Verify payment" in m.subject]
        self.assertEqual(len(admin_emails), 1)
        self.assertEqual(admin_emails[0].to, ["admin@vulor.test"])
        self.assertEqual(len(admin_emails[0].attachments), 1)
        self.assertIn(self.order.order_number, admin_emails[0].body)
        # The email must carry the staff-gated download link, never a direct
        # media URL.
        self.assertIn(
            reverse("payments:receipt_download", args=[txn.pk]),
            admin_emails[0].body,
        )

    def test_submit_invalid_receipt_keeps_order_pending(self):
        response = self._submit_receipt(filename="receipt.exe")
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")
        txn = PaymentTransaction.objects.get(order=self.order)
        self.assertEqual(txn.status, "pending")

    def test_already_submitted_order_redirects_from_instructions(self):
        self._submit_receipt()
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )

    def test_already_submitted_order_rejects_second_receipt(self):
        self._submit_receipt()
        response = self._submit_receipt()
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )
        self.assertEqual(PaymentTransaction.objects.filter(order=self.order).count(), 1)

    def test_other_users_order_is_not_accessible(self):
        other = make_user("other")
        self.client.force_login(other)
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_legacy_result_pages_redirect_to_tracking(self):
        # The legacy success/failed result URLs now redirect to the single
        # canonical result screen (orders:order_detail) rather than rendering
        # duplicate celebration templates. URLs are preserved so old links resolve.
        tracking = reverse("orders:order_detail", args=[self.order.order_number])
        for name in ("payment_success", "payment_failed"):
            response = self.client.get(reverse(f"payments:{name}", args=[self.order.id]))
            self.assertRedirects(response, tracking)


class DuplicateReceiptSubmissionRaceTests(StoreTestCase):
    """Regression tests for the _get_or_create_pending_transaction race fix:
    two requests racing to create the first pending transaction for an
    order must not surface the DB's IntegrityError as a 500 — the loser
    should transparently pick up the winner's transaction instead."""

    def setUp(self):
        self.user = make_user("racer")
        self.client.force_login(self.user)
        self.order = make_order(self.user)

    def test_get_or_create_survives_concurrent_create_race(self):
        from payments.views import _get_or_create_pending_transaction

        # Simulate the exact race window: this call's first lookup finds
        # nothing (side_effect's first value), then its own .create() hits
        # the one_active_payment_per_order constraint because another
        # request already committed the winning transaction in between —
        # the second side_effect value stands in for the recovery re-fetch.
        winner = make_transaction(self.order, status="pending")
        with patch.object(
            PaymentTransaction.objects, "latest_for", side_effect=[None, winner]
        ):
            result = _get_or_create_pending_transaction(self.order)

        self.assertEqual(result.pk, winner.pk)
        self.assertEqual(
            PaymentTransaction.objects.filter(order=self.order, status="pending").count(), 1
        )

    def test_submit_receipt_view_does_not_500_on_create_race(self):
        winner = make_transaction(self.order, status="pending")
        with patch.object(
            PaymentTransaction.objects, "latest_for", side_effect=[None, winner]
        ):
            response = self.client.post(
                reverse("payments:submit_receipt", args=[self.order.id]),
                {
                    "receipt": SimpleUploadedFile("receipt.jpg", b"receipt-bytes"),
                    "transaction_reference": "",
                },
            )
        self.assertNotEqual(response.status_code, 500)


class ReceiptAdminTests(StoreTestCase):
    def setUp(self):
        self.admin = make_user("root", is_staff=True, is_superuser=True)
        self.user = make_user("rcptuser")
        self.order = make_order(self.user, shipping_fee=Decimal("0.00"))
        self.txn = make_transaction(
            self.order,
            status="pending_verification",
            receipt=SimpleUploadedFile("receipt.jpg", b"receipt-bytes"),
        )
        self.client.force_login(self.admin)

    def test_changelist_links_to_gated_view_not_media_url(self):
        response = self.client.get(reverse("admin:payments_paymenttransaction_changelist"))
        gated_url = reverse("payments:receipt_download", args=[self.txn.pk])
        self.assertContains(response, gated_url)
        self.assertContains(response, "Download")
        self.assertNotContains(response, self.txn.receipt.url)

    def test_change_page_shows_receipt_preview(self):
        response = self.client.get(
            reverse("admin:payments_paymenttransaction_change", args=[self.txn.pk])
        )
        gated_url = reverse("payments:receipt_download", args=[self.txn.pk])
        self.assertContains(response, f'<img src="{gated_url}"')


class ReceiptDownloadTests(StoreTestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.customer = make_user("owner")
        self.order = make_order(self.customer)
        self.txn = make_transaction(
            self.order,
            status="pending_verification",
            receipt=SimpleUploadedFile("receipt.jpg", b"receipt-bytes"),
        )
        self.url = reverse("payments:receipt_download", args=[self.txn.pk])

    def test_staff_can_view_receipt(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"receipt-bytes")
        self.assertNotIn("attachment", response.get("Content-Disposition", ""))

    def test_download_flag_sets_attachment_disposition(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url + "?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_order_owner_without_staff_is_blocked(self):
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_missing_receipt_returns_404(self):
        bare_txn = make_transaction(make_order(make_user("bare")), status="pending")
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("payments:receipt_download", args=[bare_txn.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_pdf_receipt_is_always_forced_download(self):
        # PDFs are attacker-supplied files staff are required to open — they
        # must download (into a viewer the staff member chooses) rather than
        # render inline, even without the ?download flag.
        pdf_txn = make_transaction(
            make_order(make_user("pdfowner")),
            status="pending_verification",
            receipt=SimpleUploadedFile("receipt.pdf", b"%PDF-1.4"),
        )
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("payments:receipt_download", args=[pdf_txn.pk])
        )
        self.assertIn("attachment", response["Content-Disposition"])

    def test_response_headers_lock_down_receipt_content(self):
        # The per-response CSP must win over django-csp's site-wide policy,
        # and confidential bank documents must never be cached.
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(
            response["Content-Security-Policy"], "sandbox; default-src 'none'"
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")


class BodySizeLimitTests(StoreTestCase):
    """BodySizeLimitMiddleware matters most on Render, where no nginx sits in
    front to enforce client_max_body_size — an oversized body must be
    rejected from its Content-Length before Django reads any of it, not
    after the 5 MB form check has already paid for the full upload."""

    def setUp(self):
        self.user = make_user("bigposter")
        self.client.force_login(self.user)
        self.order = make_order(self.user)

    def test_oversized_body_is_rejected_before_processing(self):
        response = self.client.post(
            reverse("payments:submit_receipt", args=[self.order.id]),
            {"receipt": SimpleUploadedFile("receipt.jpg", make_test_image_bytes())},
            CONTENT_LENGTH=str(7 * 1024 * 1024),
        )
        self.assertEqual(response.status_code, 413)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")

    def test_normal_sized_body_passes(self):
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 200)


class ProductionMediaServingTests(StoreTestCase):
    """The production URLconf (vulor/urls.py, DEBUG=False branch) serves
    media directly since WhiteNoise only covers STATIC_ROOT — but payment
    receipts must stay unreachable there; they're only ever served through
    the staff-gated payments:receipt_download view.

    The DEBUG branching in vulor/urls.py happens at module import time, so
    changing settings.DEBUG alone doesn't change which urlpatterns exist —
    the urlconf module has to be reloaded under the override for the
    non-DEBUG branch to actually get built.
    """

    def setUp(self):
        self.product = make_product()

    def _reload_urlconf(self):
        import vulor.urls as urlconf

        importlib.reload(urlconf)
        clear_url_caches()

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_payment_receipts_404_but_product_media_is_served(self):
        self._reload_urlconf()
        self.addCleanup(self._reload_urlconf)

        receipt_response = self.client.get(
            "/media/payment_receipts/2026/07/anything.jpg"
        )
        self.assertEqual(receipt_response.status_code, 404)

        product_response = self.client.get(f"/media/{self.product.image.name}")
        self.assertEqual(product_response.status_code, 200)
