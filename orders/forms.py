from django import forms
from .models import Order
from .shipping import get_shipping_info


class OrderUpdateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'shipping_address', 'shipping_city', 'shipping_state', 'shipping_zipcode', 'shipping_country', 'customer_phone', 'customer_email']


class CheckoutForm(forms.Form):
    """Delivery details collected at checkout. Field names match the
    existing checkout template inputs; validation mirrors the manual
    checks in orders.views.checkout so wiring it in changes no behavior."""

    full_name = forms.CharField(max_length=200)
    phone_number = forms.CharField(max_length=20)
    email = forms.EmailField()
    address_line = forms.CharField(max_length=500)
    state = forms.CharField(max_length=100)
    city = forms.CharField(max_length=100)
    order_notes = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea,
    )

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number'].strip()
        if not phone.isdigit() or len(phone) < 10:
            raise forms.ValidationError('Invalid phone number.')
        return phone

    def clean_state(self):
        state = self.cleaned_data['state'].strip()
        if get_shipping_info(state) is None:
            raise forms.ValidationError('Select a valid delivery state.')
        return state
