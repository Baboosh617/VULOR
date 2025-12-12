from django import forms
from .models import Order


class OrderUpdateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'shipping_address', 'shipping_city', 'shipping_state', 'shipping_zipcode', 'shipping_country', 'customer_phone', 'customer_email']