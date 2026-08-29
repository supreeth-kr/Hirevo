from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import (
    User, FreelancerProfile, ClientProfile, Category, Gig, GigPackage,
    Portfolio, Certificate, Order, Delivery, Revision, Review, Message, FreelancerVerification,
    BackupAssignment
)


class BootstrapMixin:
    """Helper mixin to automatically attach Bootstrap 5 form classes to widgets."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.PasswordInput,
                               forms.NumberInput, forms.URLInput, forms.Textarea,
                               forms.Select, forms.FileInput, forms.DateInput)):
                existing_class = w.attrs.get('class', '')
                if 'form-control' not in existing_class and 'form-select' not in existing_class:
                    w.attrs['class'] = (existing_class + ' form-control').strip()
            elif isinstance(w, forms.CheckboxInput):
                w.attrs['class'] = 'form-check-input'


class RegisterForm(BootstrapMixin, UserCreationForm):
    full_name = forms.CharField(max_length=200, required=True, label='Full Name')
    email = forms.EmailField(required=True, label='Email Address')
    mobile_number = forms.CharField(max_length=15, required=True, label='Mobile Number')
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Full Address'}), required=True, label='Address')
    role = forms.ChoiceField(
        choices=[(User.ROLE_CLIENT, 'Client (Hire talent)'), (User.ROLE_FREELANCER, 'Freelancer (Offer services)')],
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        initial=User.ROLE_CLIENT,
        label='I want to join as a'
    )

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email', 'mobile_number', 'address', 'role']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists. Please sign in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data['full_name']
        user.email = self.cleaned_data['email']
        user.mobile_number = self.cleaned_data.get('mobile_number', '')
        user.address = self.cleaned_data.get('address', '')
        user.role = self.cleaned_data['role']
        # A registration is verified only after its OTP is successfully confirmed.
        user.is_email_verified = False
        if commit:
            user.save()
            if user.role == User.ROLE_CLIENT:
                ClientProfile.objects.get_or_create(user=user)
            elif user.role == User.ROLE_FREELANCER:
                FreelancerProfile.objects.get_or_create(user=user)
        return user


class OTPVerificationForm(BootstrapMixin, forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label='Enter 6-Digit OTP Code',
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••',
            'autocomplete': 'one-time-code',
            'class': 'form-control text-center fw-bold fs-3 tracking-widest',
            'maxlength': '6',
            'autofocus': 'autofocus',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}'
        })
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get('otp_code', '').strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError("Please enter a valid 6-digit numeric verification code.")
        return code


class LoginForm(BootstrapMixin, AuthenticationForm):
    pass



class FreelancerProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = FreelancerProfile
        fields = ['bio', 'skills', 'experience_years', 'hourly_rate', 'availability',
                  'languages', 'education', 'profile_picture', 'location', 'website']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your professional expertise...'}),
            'skills': forms.CheckboxSelectMultiple(),
            'education': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Degrees, institutions, certifications...'}),
            'languages': forms.TextInput(attrs={'placeholder': 'English (Fluent), Spanish (Conversational)'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. New York, USA'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://yourportfolio.com'}),
        }


class ClientProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ClientProfile
        fields = ['bio', 'location', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell freelancers about your company or projects...'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. San Francisco, USA'}),
        }


class GigForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Gig
        fields = ['title', 'category', 'description', 'tags', 'requirements', 'faqs', 'cover_image', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. I will build a modern full-stack web application'}),
            'description': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Detailed description of the services offered...'}),
            'requirements': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What do you need from the client before starting?'}),
            'faqs': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Frequently asked questions & answers...'}),
            'tags': forms.TextInput(attrs={'placeholder': 'python, django, web development, api'}),
        }


class GigPackageForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = GigPackage
        fields = ['tier', 'name', 'description', 'price', 'delivery_days', 'revisions', 'features']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Package Name (e.g. Starter, Pro, Enterprise)'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Short summary of what is included'}),
            'features': forms.TextInput(attrs={'placeholder': 'Source Code, Responsive Design, 3 Pages (comma separated)'}),
        }


class PortfolioForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ['title', 'description', 'image', 'project_url']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Project Title'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe your role and outcomes...'}),
            'project_url': forms.URLInput(attrs={'placeholder': 'https://liveproject.com'}),
        }


class CertificateForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ['name', 'issuing_organization', 'issue_date', 'description', 'certificate_file']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Certificate Name'}),
            'issuing_organization': forms.TextInput(attrs={'placeholder': 'e.g. Google, AWS, Coursera'}),
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Brief description of skills verified...'}),
        }


class OrderRequirementForm(BootstrapMixin, forms.Form):
    requirements = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Please provide all details, specifications, and project scope...'}),
        label='Project Requirements & Instructions'
    )
    attachment = forms.FileField(required=False, label='Attachment File (optional)')


class DeliveryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ['description', 'delivery_file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the work completed and instructions to view...'}),
        }


class RevisionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Revision
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detail what changes or adjustments are required...'}),
        }


class FreelancerVerificationForm(BootstrapMixin, forms.ModelForm):
    selfie_data = forms.CharField(widget=forms.HiddenInput(), required=True)
    consent = forms.BooleanField(
        required=True,
        label='I confirm this is my valid document and live photo.'
    )

    class Meta:
        model = FreelancerVerification
        fields = ['document_type', 'document_file']
        widgets = {
            'document_file': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'}),
        }

    def clean_selfie_data(self):
        data = self.cleaned_data.get('selfie_data')
        if not data or not data.startswith('data:image/'):
            raise forms.ValidationError("Please capture a live photo.")
        return data

    def clean_document_file(self):
        uploaded = self.cleaned_data.get('document_file')
        if not uploaded:
            raise forms.ValidationError('Please upload your government document.')
        if uploaded:
            if uploaded.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Government ID file must be 10 MB or smaller.')
            allowed = {'.pdf', '.jpg', '.jpeg', '.png'}
            if not any(uploaded.name.lower().endswith(ext) for ext in allowed):
                raise forms.ValidationError('Upload a PDF, JPG, or PNG government ID.')
        return uploaded


class ReviewForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(5, 0, -1)]),
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your experience working with this freelancer...'}),
        }


class MessageForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 1,
                'placeholder': 'Type a message...',
                'style': 'resize: none;',
            }),
        }


class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'description', 'icon', 'is_active']
        widgets = {
            'icon': forms.TextInput(attrs={'placeholder': 'e.g. bi-code-slash, bi-palette'}),
        }


class AssignBackupForm(BootstrapMixin, forms.Form):
    backup_freelancer = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.ROLE_FREELANCER, is_active=True),
        label='Select Backup Freelancer',
        empty_label='-- Choose a qualified freelancer --'
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        initial='Primary freelancer missed deadline. Assigned backup to ensure project continuity.',
        label='Reason for Backup Assignment'
    )


class RecommendationSearchForm(BootstrapMixin, forms.Form):
    title = forms.CharField(max_length=200, label='Project Title', widget=forms.TextInput(attrs={'placeholder': 'e.g. Build an E-commerce Website'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe project requirements...'}), label='Project Description', required=False)
    skills = forms.CharField(max_length=255, label='Required Skills (comma separated)', widget=forms.TextInput(attrs={'placeholder': 'python, django, postgresql, rest-api'}))
    budget = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label='Hourly Budget (₹/hr)', widget=forms.NumberInput(attrs={'placeholder': 'e.g. 1500'}))
    category = forms.ModelChoiceField(queryset=Category.objects.filter(is_active=True), required=False, empty_label='All Categories')
