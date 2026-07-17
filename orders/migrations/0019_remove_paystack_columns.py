from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_order_order_notes_alter_order_payment_method_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='paystack_reference',
        ),
        migrations.RemoveField(
            model_name='order',
            name='paystack_access_code',
        ),
    ]
