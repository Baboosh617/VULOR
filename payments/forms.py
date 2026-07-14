import os

from django import forms

from .models import PaymentTransaction

RECEIPT_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}
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

        return receipt
