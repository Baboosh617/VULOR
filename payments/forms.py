import io
import os

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from .models import PaymentTransaction

RECEIPT_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}
RECEIPT_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
RECEIPT_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
# Generous for any receipt photo/screenshot, but blocks decompression bombs —
# a tiny file declaring an enormous canvas would otherwise pass verify()
# (which never fully decodes) and make whoever renders it pay the memory cost.
RECEIPT_MAX_PIXELS = 25_000_000


class ReceiptUploadForm(forms.ModelForm):
    # The model field is nullable (a transaction exists before any upload),
    # so the form must make it required. transaction_reference needs no
    # override — the ModelForm derives it from the model.
    receipt = forms.FileField(
        required=True,
        error_messages={'required': 'Please upload your payment receipt.'},
    )

    class Meta:
        model = PaymentTransaction
        fields = ['receipt', 'transaction_reference']

    def clean_receipt(self):
        receipt = self.cleaned_data['receipt']

        ext = os.path.splitext(receipt.name)[1].lower()
        if ext not in RECEIPT_ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                'Receipt must be an image (JPG, PNG, WEBP) or a PDF.'
            )

        if receipt.size > RECEIPT_MAX_SIZE:
            raise forms.ValidationError('Receipt file must be 5 MB or smaller.')

        if ext in RECEIPT_IMAGE_EXTENSIONS:
            return self._clean_image(receipt)
        return self._clean_pdf(receipt)

    def _clean_image(self, receipt):
        """Validate, then re-encode — never store the customer's bytes.

        Extension/content-type are client-supplied and easy to spoof, and
        even a genuinely decodable image can carry appended payloads (image+
        archive polyglots) or EXIF metadata (camera GPS puts the customer's
        location in a file staff download and email). Decoding and re-saving
        through Pillow keeps only the pixels: neither survives the round trip.
        """
        invalid = forms.ValidationError(
            'This file is not a valid image. Please upload a photo '
            'or screenshot of your receipt.'
        )
        try:
            Image.open(receipt).verify()
        except Exception:
            raise invalid

        # verify() consumes the stream and invalidates the parser — rewind
        # and reopen for the real decode. Don't close these Image objects:
        # closing would close the underlying in-memory upload too.
        receipt.seek(0)
        try:
            img = Image.open(receipt)
            width, height = img.size
            if width * height > RECEIPT_MAX_PIXELS:
                raise forms.ValidationError(
                    'This image is too large. Please upload a smaller photo '
                    'or screenshot of your receipt.'
                )
            out = io.BytesIO()
            img.convert('RGB').save(out, format='JPEG', quality=85)
        except forms.ValidationError:
            raise
        except Exception:
            raise invalid

        return SimpleUploadedFile(
            os.path.splitext(receipt.name)[0] + '.jpg',
            out.getvalue(),
            content_type='image/jpeg',
        )

    def _clean_pdf(self, receipt):
        # Deliberately shallow — the magic-byte check stops arbitrary files
        # renamed .pdf without pulling in a PDF-parsing dependency (real bank
        # PDFs failing a strict parse would block real payments). Defending
        # the staff member who opens these is the download view's job:
        # payments:receipt_download forces PDFs to download under a locked
        # CSP instead of rendering them.
        head = receipt.read(5)
        receipt.seek(0)
        if head != b'%PDF-':
            raise forms.ValidationError(
                'This file is not a valid PDF. Please upload your bank\'s '
                'receipt file or a photo of the receipt.'
            )
        return receipt
