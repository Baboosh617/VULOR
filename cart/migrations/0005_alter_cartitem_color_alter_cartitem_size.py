from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0004_alter_cartitem_color_alter_cartitem_quantity_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cartitem',
            name='color',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='cartitem',
            name='size',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
