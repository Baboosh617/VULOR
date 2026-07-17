from django.conf import settings


def get_bank_details():
    """The store's transfer account, as template context keys. Used by the
    transfer-instructions page and the customer email context — the two must
    always show the same account."""
    return {
        'bank_name': settings.BANK_TRANSFER_BANK_NAME,
        'account_name': settings.BANK_TRANSFER_ACCOUNT_NAME,
        'account_number': settings.BANK_TRANSFER_ACCOUNT_NUMBER,
    }
