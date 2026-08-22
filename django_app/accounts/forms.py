from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, EmailOTP

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    country = forms.CharField(max_length=100, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    image = forms.URLField(required=False, label='Profile Image URL')
    role = forms.ChoiceField(
        choices=[('client', 'Client'), ('freelancer', 'Freelancer')],
        widget=forms.RadioSelect,
        required=True,
        label='I am a'
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'phone', 'country', 'description', 'image', 'password1', 'password2']


class EmailVerificationForm(forms.Form):
    otp = forms.CharField(
        max_length=10,
        min_length=4,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 6-digit OTP',
            'class': 'form-control',
            'autocomplete': 'off'
        }),
        label='OTP'
    )


class ResendOTPForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )


class LoginForm(AuthenticationForm):
    pass


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'country', 'description', 'image', 'is_seller']
