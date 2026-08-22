from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm, LoginForm, ProfileForm, EmailVerificationForm, ResendOTPForm
from .email_utils import send_otp_email, verify_otp
from hirevo.form_utils import add_bootstrap_classes

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    role = request.POST.get('role', 'client')
    form = RegisterForm(request.POST or None)
    add_bootstrap_classes(form)
    
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.is_seller = (role == 'freelancer')
        user.email_verified = False
        user.save()
        
        # Send OTP to user's email
        try:
            send_otp_email(user.email)
            # Store user email in session for verification
            request.session['email_to_verify'] = user.email
            request.session['user_id_temp'] = user.id
            messages.info(request, f'An OTP has been sent to {user.email}. Please verify to complete registration.')
            return redirect('verify-email')
        except Exception as e:
            messages.error(request, f'Failed to send OTP. Error: {str(e)}')
            user.delete()
            return redirect('register')
    
    return render(request, 'accounts/register.html', {'form': form, 'role': role})


def verify_email_view(request):
    """Verify email with OTP during registration"""
    if request.user.is_authenticated:
        return redirect('home')
    
    email = request.session.get('email_to_verify')
    user_id = request.session.get('user_id_temp')
    
    if not email or not user_id:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')
    
    form = EmailVerificationForm(request.POST or None)
    add_bootstrap_classes(form)
    
    if request.method == 'POST' and form.is_valid():
        otp = form.cleaned_data.get('otp')
        is_valid, otp_record = verify_otp(email, otp)
        
        if is_valid:
            # Update user's email verification status
            from .models import User
            try:
                user = User.objects.get(id=user_id)
                user.email_verified = True
                from django.utils import timezone
                user.email_verified_at = timezone.now()
                user.save()
                
                # Clear session
                if 'email_to_verify' in request.session:
                    del request.session['email_to_verify']
                if 'user_id_temp' in request.session:
                    del request.session['user_id_temp']
                
                messages.success(request, 'Email verified successfully! You can now login.')
                # Login the user automatically
                login(request, user)
                return redirect('home')
            except Exception as e:
                messages.error(request, f'Error verifying email: {str(e)}')
        else:
            messages.error(request, 'Invalid or expired OTP. Please try again.')
    
    context = {
        'form': form,
        'email': email,
    }
    return render(request, 'accounts/verify_email.html', context)


def resend_otp_view(request):
    """Resend OTP if user didn't receive it"""
    if request.user.is_authenticated:
        return redirect('home')
    
    email = request.session.get('email_to_verify')
    
    if request.method == 'POST':
        try:
            send_otp_email(email)
            messages.success(request, 'OTP has been resent to your email.')
        except Exception as e:
            messages.error(request, f'Failed to resend OTP. Error: {str(e)}')
        return redirect('verify-email')
    
    return redirect('verify-email')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    login_type = request.POST.get('login_type', 'client')
    form = LoginForm(request, data=request.POST or None)
    add_bootstrap_classes(form)
    error = None
    
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        
        # Check if email is verified
        if not user.email_verified:
            messages.warning(request, 'Please verify your email before logging in.')
            request.session['email_to_verify'] = user.email
            request.session['user_id_temp'] = user.id
            return redirect('verify-email')
        
        if login_type == 'freelancer' and not user.is_seller:
            error = 'This account is not registered as a freelancer.'
        elif login_type == 'client' and user.is_seller:
            error = 'This is a freelancer account. Please use Freelancer Login.'
        else:
            login(request, user)
            return redirect('home')
    
    return render(request, 'accounts/login.html', {
        'form': form,
        'login_type': login_type,
        'error': error,
    })


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    add_bootstrap_classes(form)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated!')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'form': form})
