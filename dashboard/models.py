from django.db import models


FIT_CHOICES = (
    ('loose', 'Loose'),
    ('fitted', 'Fitted'),
)

fit_type = models.CharField(max_length=20, choices=FIT_CHOICES, blank=True, null=True)
