from django.db import migrations


def remap_initiated_to_failed(apps, schema_editor):
    """Close out Paystack-era 'initiated' transactions.

    0009 removed 'initiated' from the status choices and from the
    one-active-payment-per-order constraint, but left any existing rows
    untouched — they would sit invisible to latest_for() while no longer
    blocking a duplicate transaction. They were payment inits that never
    completed, so 'failed' (outside the active-constraint statuses) is the
    correct and constraint-safe terminal state.
    """
    PaymentTransaction = apps.get_model('payments', 'PaymentTransaction')
    PaymentTransaction.objects.filter(status='initiated').update(status='failed')


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0010_performance_indexes'),
    ]

    operations = [
        migrations.RunPython(remap_initiated_to_failed, migrations.RunPython.noop),
    ]
