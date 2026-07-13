import os

from django import forms

from .models import PaymentTransaction

RECEIPT_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}
RECEIPT_MAX_SIZE = 5 * 1024 * 1024  # 5 MB


class ReceiptUploadForm(forms.ModelForm):
    receipt = forms.FileField(
        required=True,
        error_messages={'required': 'Please upload your payment receipt.'},
    )
    transaction_reference = forms.CharField(
        required=False,
        max_length=100,
        strip=True,
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
