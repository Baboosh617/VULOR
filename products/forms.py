# In your products/forms.py or reviews/forms.py
from django import forms
from .models import Review
from django.core.exceptions import ValidationError

class ReviewForm(forms.ModelForm):
    RATING_CHOICES = [
        (5, '★★★★★'),
        (4, '★★★★'),
        (3, '★★★'),
        (2, '★★'),
        (1, '★'),
    ]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
        label='Your Rating'
    )
    
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Share your experience with our products...',
                'class': 'w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-purple-500'
            }),
        }
        labels = {
            'comment': 'Your Review',
        }
    def clean_rating(self):
        rating = int(self.cleaned_data.get('rating'))
        if rating not in [1, 2, 3, 4, 5]:
            raise ValidationError("Please select a rating between 1 and 5.")
        return rating
    def clean_comment(self):
        comment = self.cleaned_data.get('comment')
        if len(comment) < 10:
            raise ValidationError("Your review must be at least 10 characters long.")
        return comment