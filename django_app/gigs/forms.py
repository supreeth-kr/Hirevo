from django import forms
from .models import Gig, GigImage

class GigForm(forms.ModelForm):
    class Meta:
        model = Gig
        fields = ['title', 'description', 'short_title', 'short_desc', 'category', 'price', 'cover', 'delivery_time', 'revision_number', 'features']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'features': forms.TextInput(attrs={'placeholder': 'e.g. Logo design, Source file, High resolution'}),
            'cover': forms.URLInput(attrs={'placeholder': 'https://...'}),
        }

class GigImageForm(forms.ModelForm):
    class Meta:
        model = GigImage
        fields = ['image']
