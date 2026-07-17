from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0007_remove_payment_user_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='paymenttransaction',
            old_name='paystack_reference',
            new_name='reference',
        ),
        migrations.RemoveField(
            model_name='paymenttransaction',
            name='paystack_access_code',
        ),
    ]
