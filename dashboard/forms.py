# dashboard/forms.py
from django import forms
from products.models import Product

class ProductForm(forms.ModelForm):
    # Custom field for slug
    slug = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'border rounded p-2 w-full bg-gray-100',
            'readonly': 'readonly',
            'id': 'id_slug',
        }),
        help_text="Auto-generated slug based on product name"
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'slug', 'description',
            'price', 'compare_price',
            'category', 'fit_type',
            'image', 'inventory_count',
            'is_active', 'featured',
            'available_sizes', 'available_colors',
            'waist_measurements', 'hip_measurements',
            'length_measurements', 'thigh_measurements', 'rise_measurements',
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'border rounded p-2 w-full', 
                'id': 'id_name',
                'placeholder': 'Enter product name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'border rounded p-2 w-full', 
                'rows': 4,
                'placeholder': 'Enter detailed product description'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'border rounded p-2 w-full', 
                'step': '0.01',
                'id': 'id_price',
                'placeholder': '0.00'
            }),
            'compare_price': forms.NumberInput(attrs={
                'class': 'border rounded p-2 w-full', 
                'step': '0.01',
                'id': 'id_compare_price',
                'placeholder': '0.00 (optional)'
            }),
            'category': forms.Select(attrs={
                'class': 'border rounded p-2 w-full', 
                'id': 'id_category'
            }),
            'fit_type': forms.Select(attrs={
                'class': 'border rounded p-2 w-full', 
                'id': 'id_fit_type'
            }),
            'available_sizes': forms.TextInput(attrs={
                'class': 'border rounded p-2 w-full', 
                'id': 'id_available_sizes',
                'placeholder': 'S,M,L,XL or 28,30,32'
            }),
            'available_colors': forms.TextInput(attrs={
                'class': 'border rounded p-2 w-full', 
                'id': 'id_available_colors',
                'placeholder': 'Black,White,Navy'
            }),
            'image': forms.FileInput(attrs={
                'class': 'border rounded p-2 w-full file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
            }),
            'inventory_count': forms.NumberInput(attrs={
                'class': 'border rounded p-2 w-full',
                'min': '0',
                'placeholder': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 text-blue-600 rounded'
            }),
            'featured': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 text-blue-600 rounded'
            }),
            'waist_measurements': forms.Textarea(attrs={
                'class': 'border rounded p-2 w-full', 
                'rows': 3,
                'placeholder': 'e.g., 28: 28", 30: 30", 32: 32"'
            }),
            'hip_measurements': forms.Textarea(attrs={
                'class': 'border rounded p-2 w-full', 
                'rows': 3,
                'placeholder': 'e.g., 28: 34", 30: 36", 32: 38"'
            }),
            'length_measurements': forms.Textarea(attrs={
                'class': 'border rounded p-2 w-full', 
                'rows': 3,
                'placeholder': 'e.g., 28: 40", 30: 40", 32: 40"'
            }),
            'thigh_measurements': forms.Textarea(attrs={
                'class': 'border rounded p-2 w-full', 
                'rows': 3,
                'placeholder': 'e.g., 28: 22", 30: 23", 32: 24"'
            }),
            'rise_measurements': forms.Textarea(attrs={
                'class': 'border rounded p-2 w-full', 
                'rows': 3,
                'placeholder': 'e.g., 28: 10", 30: 10.5", 32: 11"'
            }),
        }
        
        help_texts = {
            'available_sizes': 'Comma-separated sizes (e.g., S,M,L,XL or 28,30,32)',
            'available_colors': 'Comma-separated colors (e.g., Black,White,Navy)',
            'compare_price': 'Original price to show as "on sale" (optional)',
            'inventory_count': 'Number of items currently in stock',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set empty choice for fit_type
        self.fields['fit_type'].choices = [('', '---------')] + Product.FIT_CHOICES
        if self.instance and self.instance.pk:
            self.fields['slug'].initial = self.instance.slug
        else:
            self.fields['slug'].initial = ""

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        
        # Fit type validation
        if category == 'cargo-jeans' and not cleaned.get('fit_type'):
            self.add_error('fit_type', 'Fit type is required for cargo jeans.')
        elif category != 'cargo-jeans':
            cleaned['fit_type'] = None
        
        # Clear measurements if not cargo-jeans or sweatpants
        if category not in ['cargo-jeans', 'sweatpants']:
            measurement_fields = [
                'waist_measurements',
                'hip_measurements', 
                'length_measurements',
                'thigh_measurements',
                'rise_measurements',
            ]
            for field in measurement_fields:
                cleaned[field] = ''
        
        # Size validation
        sizes = cleaned.get('available_sizes', '')
        if not sizes or sizes.strip() == '':
            self.add_error('available_sizes', 'Please specify available sizes.')
        
        # Color validation
        colors = cleaned.get('available_colors', '')
        if not colors or colors.strip() == '':
            self.add_error('available_colors', 'Please specify available colors.')
        
        # Price validation
        price = cleaned.get('price')
        compare_price = cleaned.get('compare_price')
        if compare_price is not None and price is not None:
            if compare_price < price:
                self.add_error('compare_price', 'Compare price should be greater than or equal to price.')
        
        # Inventory validation
        inv = cleaned.get('inventory_count')
        if inv is not None and inv < 0:
            self.add_error('inventory_count', 'Inventory count cannot be negative.')
        
        return cleaned
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle sizes and colors formatting
        if self.cleaned_data.get('available_sizes'):
            sizes = self.cleaned_data['available_sizes']
            sizes = [s.strip().upper() for s in sizes.split(',') if s.strip()]
            instance.available_sizes = ','.join(sizes)
        
        if self.cleaned_data.get('available_colors'):
            colors = self.cleaned_data['available_colors']
            colors = [c.strip().title() for c in colors.split(',') if c.strip()]
            instance.available_colors = ','.join(colors)
        
        if commit:
            instance.save()
        
        return instance