import os

from django import forms
from PIL import Image

from .models import PaymentTransaction

RECEIPT_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}
RECEIPT_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
RECEIPT_MAX_SIZE = 5 * 1024 * 1024  # 5 MB


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

        # Extension/content-type are client-supplied and easy to spoof —
        # actually decode the image structure so a renamed non-image file
        # can't pass as a receipt. PDFs are left to the extension+size check
        # above (no content-sniffing dependency added for those here).
        if ext in RECEIPT_IMAGE_EXTENSIONS:
            receipt.seek(0)
            try:
                Image.open(receipt).verify()
            except Exception:
                raise forms.ValidationError(
                    'This file is not a valid image. Please upload a photo '
                    'or screenshot of your receipt.'
                )
            finally:
                # verify() consumes the stream; reset it or Django saves a
                # truncated file.
                receipt.seek(0)

        return receipt
