from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import (User, FreelancerProfile, ClientProfile, Gig, GigPackage,
                     Portfolio, Certificate, Order, Delivery, Revision, Review, Message)


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.PasswordInput,
                               forms.NumberInput, forms.URLInput, forms.Textarea,
                               forms.Select, forms.FileInput, forms.DateInput)):
                w.attrs['class'] = w.attrs.get('class', '') + ' form-control'
            elif isinstance(w, forms.CheckboxInput):
                w.attrs['class'] = 'form-check-input'


class RegisterForm(BootstrapMixin, UserCreationForm):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=[('client', 'Client'), ('freelancer', 'Freelancer')],
                              widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email', 'role', 'password1', 'password2']


class LoginForm(BootstrapMixin, AuthenticationForm):
    pass


class FreelancerProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = FreelancerProfile
        fields = ['bio', 'skills', 'experience_years', 'hourly_rate', 'availability',
                  'languages', 'education', 'profile_picture', 'location', 'website']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'skills': forms.CheckboxSelectMultiple(),
            'education': forms.Textarea(attrs={'rows': 3}),
        }


class ClientProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ClientProfile
        fields = ['bio', 'location', 'profile_picture']
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}


class GigForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Gig
        fields = ['title', 'category', 'description', 'tags', 'requirements', 'faqs', 'cover_image', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'requirements': forms.Textarea(attrs={'rows': 3}),
            'faqs': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'python, django, web development'}),
        }


class GigPackageForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = GigPackage
        fields = ['tier', 'name', 'description', 'price', 'delivery_days', 'revisions', 'features']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'features': forms.TextInput(attrs={'placeholder': 'Feature 1, Feature 2'}),
        }


class PortfolioForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ['title', 'description', 'image_url', 'project_url']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class CertificateForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ['name', 'issuing_organization', 'issue_date', 'description', 'certificate_url']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class OrderRequirementsForm(BootstrapMixin, forms.Form):
    requirements = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
                                    label='Project Requirements')
    attachment_url = forms.URLField(required=False, label='Attachment URL (optional)')


class DeliveryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ['description', 'file_url']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class RevisionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Revision
        fields = ['reason']
        widgets = {'reason': forms.Textarea(attrs={'rows': 4})}


class ReviewForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 4}),
        }


class MessageForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type your message...'})}


class RecommendationSearchForm(BootstrapMixin, forms.Form):
    title = forms.CharField(max_length=200, label='Project Title')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='Project Description')
    skills = forms.CharField(max_length=255, label='Required Skills (comma separated)',
                              widget=forms.TextInput(attrs={'placeholder': 'python, django, mysql'}))
    budget = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label='Budget (₹/hr)')
    category = forms.CharField(max_length=100, required=False)
