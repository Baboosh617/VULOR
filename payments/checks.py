from django.conf import settings
from django.core import checks


@checks.register()
def bank_details_configured(app_configs, **kwargs):
    """Fail the Render build if the bank-transfer env vars are missing.

    The settings default these to '' — without this check a deploy with the
    vars unset goes live and shows customers a transfer page with blank bank
    name and account number. Errors abort `manage.py migrate` in the Render
    buildCommand, so the deploy fails loudly instead. Keyed on ON_RENDER so
    local dev and the SQLite test run are unaffected.
    """
    if not getattr(settings, 'ON_RENDER', False):
        return []
    errors = []
    for setting_name in (
        'BANK_TRANSFER_BANK_NAME',
        'BANK_TRANSFER_ACCOUNT_NAME',
        'BANK_TRANSFER_ACCOUNT_NUMBER',
    ):
        if not getattr(settings, setting_name, ''):
            errors.append(
                checks.Error(
                    f'{setting_name} is not set.',
                    hint=(
                        'Set it in the Render service environment — the '
                        'bank-transfer page and payment emails render these '
                        'values to paying customers.'
                    ),
                    id='payments.E001',
                )
            )
    return errors
