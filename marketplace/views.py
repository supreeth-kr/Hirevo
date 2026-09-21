import secrets
import razorpay
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, JsonResponse, FileResponse
from django.forms import modelformset_factory
from django.views.decorators.csrf import csrf_exempt

from .models import (
    User, Category, Skill, FreelancerProfile, ClientProfile,
    Portfolio, Certificate, Gig, GigPackage, Order, Delivery,
    Revision, RevisionCharge, Payment, Review, Message, Notification, Penalty,
    BackupAssignment, ProjectHistory, EmailVerificationOTP, FreelancerVerification
)
from .forms import (
    RegisterForm, LoginForm, FreelancerProfileForm, ClientProfileForm,
    GigForm, GigPackageForm, PortfolioForm, CertificateForm,
    OrderRequirementForm, DeliveryForm, RevisionForm, ReviewForm,
    MessageForm, CategoryForm, AssignBackupForm, RecommendationSearchForm,
    OTPVerificationForm, FreelancerVerificationForm
)
from .permissions import client_required, freelancer_required, admin_required
from .services import (
    create_notification, add_project_history, check_and_apply_delays,
    assign_backup_freelancer, calculate_freelancer_earnings,
    GovernmentIDVerificationService
)
from .ai_recommendation import recommend_freelancers, recommend_gigs
from .emails import send_registration_otp_email


def _mask_email(email):
    """Helper to mask an email address for public display (e.g., j***e@domain.com)."""
    if not email or '@' not in email:
        return email
    local_part, domain = email.split('@', 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + '***'
    else:
        masked_local = local_part[0] + '***' + local_part[-1]
    return f"{masked_local}@{domain}"


# ==========================================
# AUTHENTICATION & OTP VIEWS
# ==========================================

def register_view(request):
    """
    Step 1 of registration:
    Validates form inputs, stages registration data in session,
    generates a 6-digit cryptographic OTP, dispatches email, and redirects to verification.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Build pending user without committing to DB yet
            user = form.save(commit=False)
            
            # Stage registration data safely in session
            request.session['pending_registration'] = {
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'password_hash': user.password,
                'mobile_number': user.mobile_number,
                'address': user.address,
            }

            # Generate 6-digit OTP
            otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
            expires_at = timezone.now() + timezone.timedelta(minutes=10)

            # Invalidate any older unverified registration OTPs for this email
            EmailVerificationOTP.objects.filter(
                email__iexact=user.email,
                purpose=EmailVerificationOTP.PURPOSE_REGISTRATION,
                is_verified=False
            ).delete()

            EmailVerificationOTP.objects.create(
                email=user.email,
                otp_code=otp_code,
                purpose=EmailVerificationOTP.PURPOSE_REGISTRATION,
                expires_at=expires_at
            )

            # Dispatch OTP Email
            send_registration_otp_email(
                email=user.email,
                full_name=user.full_name or user.username,
                otp_code=otp_code,
                expiry_minutes=10
            )

            messages.info(
                request,
                f"We've sent a 6-digit verification code to {user.email}. Please verify your email to complete registration."
            )
            return redirect('verify_otp')
        else:
            messages.error(request, "Please correct the errors in the registration form.")
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def verify_otp_view(request):
    """
    Step 2 of registration:
    Validates the 6-digit OTP code against the database.
    Upon successful verification, creates the User, role profile, and logs user in.
    """
    if request.user.is_authenticated:
        return redirect('home')

    pending = request.session.get('pending_registration')
    if not pending:
        messages.warning(request, "No pending registration found. Please register first.")
        return redirect('register')

    email = pending.get('email')
    masked_email = _mask_email(email)

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['otp_code']
            otp_record = EmailVerificationOTP.objects.filter(
                email__iexact=email,
                purpose=EmailVerificationOTP.PURPOSE_REGISTRATION,
                is_verified=False
            ).first()

            if not otp_record:
                form.add_error('otp_code', "No active verification code found. Please request a new one.")
            else:
                is_valid, err_msg = otp_record.is_valid(code)
                if not is_valid:
                    form.add_error('otp_code', err_msg)
                else:
                    # Mark OTP as verified
                    otp_record.is_verified = True
                    otp_record.save(update_fields=['is_verified'])

                    # Check for username / email conflict edge cases
                    if User.objects.filter(username__iexact=pending['username']).exists() or \
                       User.objects.filter(email__iexact=pending['email']).exists():
                        messages.error(request, "An account with these credentials was already created. Please log in.")
                        request.session.pop('pending_registration', None)
                        return redirect('login')

                    # Create user account
                    user = User.objects.create(
                        username=pending['username'],
                        email=pending['email'],
                        full_name=pending['full_name'],
                        role=pending['role'],
                        password=pending['password_hash'],
                        mobile_number=pending.get('mobile_number', ''),
                        address=pending.get('address', ''),
                        is_active=True,
                        is_email_verified=True
                    )

                    # Create associated profile
                    if user.role == User.ROLE_CLIENT:
                        ClientProfile.objects.get_or_create(user=user)
                    elif user.role == User.ROLE_FREELANCER:
                        FreelancerProfile.objects.get_or_create(user=user)

                    # Clear session staging
                    request.session.pop('pending_registration', None)
                    request.session.pop('aadhaar_verified', None)

                    # Auto login
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    messages.success(
                        request,
                        f"Email verified successfully! Welcome to Hirevo, {user.full_name or user.username}."
                    )

                    if user.is_client():
                        return redirect('client_dashboard')
                    elif user.is_freelancer():
                        # Redirect directly to identity verification for onboarding
                        return redirect('freelancer_verification')
                    return redirect('home')
    else:
        form = OTPVerificationForm()

    return render(request, 'accounts/verify_otp.html', {
        'form': form,
        'masked_email': masked_email
    })


def resend_otp_view(request):
    """
    Resend verification code to the pending user's email with cooldown check.
    """
    if request.user.is_authenticated:
        return redirect('home')

    pending = request.session.get('pending_registration')
    if not pending:
        messages.warning(request, "No pending registration found. Please register first.")
        return redirect('register')

    email = pending.get('email')
    full_name = pending.get('full_name') or pending.get('username')

    # Rate limiting: check if last OTP was created less than 45 seconds ago
    recent_otp = EmailVerificationOTP.objects.filter(
        email__iexact=email,
        purpose=EmailVerificationOTP.PURPOSE_REGISTRATION,
        created_at__gte=timezone.now() - timezone.timedelta(seconds=45)
    ).first()

    if recent_otp:
        messages.warning(request, "Please wait a moment before requesting another verification code.")
        return redirect('verify_otp')

    # Invalidate older unverified codes
    EmailVerificationOTP.objects.filter(
        email__iexact=email,
        purpose=EmailVerificationOTP.PURPOSE_REGISTRATION,
        is_verified=False
    ).delete()

    new_code = f"{secrets.randbelow(900000) + 100000:06d}"
    expires_at = timezone.now() + timezone.timedelta(minutes=10)

    EmailVerificationOTP.objects.create(
        email=email,
        otp_code=new_code,
        purpose=EmailVerificationOTP.PURPOSE_REGISTRATION,
        expires_at=expires_at
    )

    send_registration_otp_email(
        email=email,
        full_name=full_name,
        otp_code=new_code,
        expiry_minutes=10
    )

    messages.success(request, f"A fresh 6-digit verification code has been dispatched to {email}.")
    return redirect('verify_otp')



def login_view(request):
    """
    Standard user authentication view with two role options:
    - Login as Client (for hiring talent and managing projects)
    - Login as Freelancer (for offering services and submitting work)
    """
    if request.user.is_authenticated:
        if request.user.is_admin_user():
            return redirect('admin_dashboard')
        elif request.user.is_client():
            return redirect('client_dashboard')
        elif request.user.is_freelancer():
            return redirect('freelancer_dashboard')
        return redirect('home')

    # Detect selected role tab from POST or GET (default to client)
    selected_role = request.POST.get('selected_role') or request.GET.get('role', 'client')
    if selected_role not in ['client', 'freelancer']:
        selected_role = 'client'

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Please contact platform administrators.")
                return render(request, 'accounts/login.html', {
                    'form': form,
                    'selected_role': selected_role,
                    'next': request.GET.get('next') or request.POST.get('next', '')
                })
            
            # The standard portal must never authenticate an administrator, and
            # each role tab accepts only the matching account type.
            if user.is_admin_user():
                messages.error(request, "Administrator accounts must use the Administrator Portal.")
                return render(request, 'accounts/login.html', {'form': form, 'selected_role': selected_role, 'next': request.POST.get('next', '')})
            if user.role != selected_role:
                messages.error(request, f"This account is registered as a {user.get_role_display()}. Please use the matching login portal.")
                return render(request, 'accounts/login.html', {'form': form, 'selected_role': selected_role, 'next': request.POST.get('next', '')})

            login(request, user)
            messages.success(request, f"Welcome back, {user.full_name or user.username}!")
            
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            
            if user.is_admin_user():
                return redirect('admin_dashboard')
            elif user.is_client():
                return redirect('client_dashboard')
            elif user.is_freelancer():
                return redirect('freelancer_dashboard')
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password. Please check your credentials.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'selected_role': selected_role,
        'next': request.GET.get('next', '')
    })


def admin_login_view(request):
    """
    Dedicated, isolated login view for Platform Administrators and Staff.
    Authenticates superusers/staff and directs them straight to the Admin Operations Center.
    """
    if request.user.is_authenticated:
        if request.user.is_admin_user():
            return redirect('admin_dashboard')
        else:
            messages.warning(
                request,
                f"You are currently logged in as a non-administrator account ({request.user.username}). "
                "Please log out first to access the Administrator Security Portal."
            )
            return render(request, 'accounts/admin_login.html', {
                'form': LoginForm(),
                'is_admin_portal': True,
                'logged_in_non_admin': True,
            })

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, "This administrator account is currently inactive. Please contact system support.")
                return render(request, 'accounts/admin_login.html', {'form': form, 'is_admin_portal': True})
            
            # Enforce administrator verification
            if not (user.is_admin_user() or user.is_staff or user.is_superuser):
                messages.error(
                    request,
                    "Access Denied: This portal is strictly restricted to platform administrators and staff. "
                    "If you are a client or freelancer, please use the standard portal."
                )
                return render(request, 'accounts/admin_login.html', {
                    'form': form,
                    'is_admin_portal': True,
                    'access_denied': True
                })
            
            login(request, user)
            messages.success(request, f"Administrator Session Initiated. Welcome, {user.full_name or user.username}!")
            
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and '/admin-dashboard/' in next_url:
                return redirect(next_url)
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid administrator credentials.")
    else:
        form = LoginForm()

    return render(request, 'accounts/admin_login.html', {
        'form': form,
        'is_admin_portal': True,
        'next': request.GET.get('next', '')
    })


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')


def password_reset_request_view(request):
    """
    Handle forgot password request:
    1. User enters email
    2. System generates 6-digit OTP and sends via email
    3. Redirect to OTP verification page
    """
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return redirect('password_reset')
        
        from marketplace.models import User, EmailVerificationOTP
        from marketplace.emails import send_password_reset_otp_email
        import random, string
        from datetime import timedelta
        from django.utils import timezone
        
        try:
            # Check if user exists
            user = User.objects.get(email=email)
            
            # Generate 6-digit OTP
            otp_code = ''.join(random.choices(string.digits, k=6))
            
            # Create OTP record
            otp_record = EmailVerificationOTP.objects.create(
                email=email,
                otp_code=otp_code,
                purpose=EmailVerificationOTP.PURPOSE_PASSWORD_RESET,
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            
            # Send OTP email
            send_password_reset_otp_email(email, user.full_name or user.username, otp_code)
            
            # Store in session for verification page
            request.session['reset_email'] = email
            request.session['reset_user_id'] = user.id
            
            messages.success(request, f'A password reset code has been sent to {email}.')
            return redirect('verify_reset_otp')
            
        except User.DoesNotExist:
            # Security: Don't reveal if email exists or not
            messages.info(request, f'If an account exists with {email}, a password reset code has been sent.')
            return redirect('login')
        except Exception as e:
            print(f"❌ ERROR in password reset: {str(e)}")
            messages.error(request, f'Error sending reset code: {str(e)}')
            return redirect('password_reset')
    
    return render(request, 'accounts/password_reset.html')


def verify_reset_otp_view(request):
    """Verify password reset OTP code."""
    email = request.session.get('reset_email')
    user_id = request.session.get('reset_user_id')
    
    if not email or not user_id:
        messages.error(request, 'Session expired. Please request a new password reset.')
        return redirect('password_reset')
    
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '').strip()
        
        from marketplace.models import EmailVerificationOTP
        from django.utils import timezone
        
        try:
            otp_record = EmailVerificationOTP.objects.get(
                email=email,
                otp_code=otp_code,
                purpose=EmailVerificationOTP.PURPOSE_PASSWORD_RESET,
                expires_at__gt=timezone.now(),
                is_verified=False
            )
            
            # Mark OTP as verified
            otp_record.is_verified = True
            otp_record.save()
            
            # Store verification in session
            request.session['reset_otp_verified'] = True
            
            messages.success(request, 'OTP verified successfully. Please set your new password.')
            return redirect('reset_password')
            
        except EmailVerificationOTP.DoesNotExist:
            messages.error(request, 'Invalid or expired OTP. Please try again.')
            return redirect('verify_reset_otp')
    
    context = {'email': email}
    return render(request, 'accounts/verify_reset_otp.html', context)


def reset_password_view(request):
    """Handle new password entry after OTP verification."""
    email = request.session.get('reset_email')
    user_id = request.session.get('reset_user_id')
    otp_verified = request.session.get('reset_otp_verified', False)
    
    if not email or not user_id or not otp_verified:
        messages.error(request, 'Invalid session. Please request a new password reset.')
        return redirect('password_reset')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()
        
        if not password1 or not password2:
            messages.error(request, 'Please enter and confirm your password.')
            return redirect('reset_password')
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('reset_password')
        
        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('reset_password')
        
        try:
            from marketplace.models import User
            user = User.objects.get(id=user_id, email=email)
            user.set_password(password1)
            user.save()
            
            # Clear session data
            for key in ['reset_email', 'reset_user_id', 'reset_otp_verified']:
                if key in request.session:
                    del request.session[key]
            
            messages.success(request, 'Your password has been reset successfully. Please login with your new password.')
            return redirect('login')
            
        except User.DoesNotExist:
            messages.error(request, 'User not found. Please try again.')
            return redirect('password_reset')
        except Exception as e:
            print(f"❌ ERROR resetting password: {str(e)}")
            messages.error(request, f'Error resetting password: {str(e)}')
            return redirect('reset_password')
    
    context = {'email': email}
    return render(request, 'accounts/reset_password.html', context)


# ==========================================
# PUBLIC MARKETPLACE VIEWS
# ==========================================

def home_view(request):
    categories = Category.objects.filter(is_active=True)
    popular_gigs = Gig.objects.filter(status=Gig.STATUS_ACTIVE).select_related(
        'freelancer', 'category'
    ).prefetch_related('packages')[:8]

    top_freelancers = FreelancerProfile.objects.filter(
        user__is_active=True
    ).select_related('user').prefetch_related('skills')[:4]

    stats = {
        'total_gigs': Gig.objects.filter(status=Gig.STATUS_ACTIVE).count(),
        'total_freelancers': User.objects.filter(role=User.ROLE_FREELANCER, is_active=True).count(),
        'completed_orders': Order.objects.filter(status=Order.STATUS_COMPLETED).count(),
    }

    return render(request, 'home.html', {
        'categories': categories,
        'popular_gigs': popular_gigs,
        'top_freelancers': top_freelancers,
        'stats': stats,
    })


def gig_list_view(request):
    gigs = Gig.objects.filter(status=Gig.STATUS_ACTIVE).select_related('freelancer', 'category').prefetch_related('packages')

    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    delivery_days = request.GET.get('delivery_days', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    if query:
        gigs = gigs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query) |
            Q(freelancer__username__icontains=query) |
            Q(freelancer__full_name__icontains=query) |
            Q(freelancer__freelancer_profile__skills__name__icontains=query)
        ).distinct()

    if category_slug:
        gigs = gigs.filter(category__slug=category_slug)

    if min_price:
        try:
            gigs = gigs.filter(packages__price__gte=float(min_price)).distinct()
        except ValueError:
            pass

    if max_price:
        try:
            gigs = gigs.filter(packages__price__lte=float(max_price)).distinct()
        except ValueError:
            pass

    if delivery_days:
        try:
            gigs = gigs.filter(packages__delivery_days__lte=int(delivery_days)).distinct()
        except ValueError:
            pass

    if sort_by == 'price_low':
        gigs = gigs.order_by('packages__price').distinct()
    elif sort_by == 'price_high':
        gigs = gigs.order_by('-packages__price').distinct()
    elif sort_by == 'oldest':
        gigs = gigs.order_by('created_at')
    else:
        gigs = gigs.order_by('-created_at')

    paginator = Paginator(gigs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(is_active=True)

    return render(request, 'gigs/list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'query': query,
        'category_slug': category_slug,
        'min_price': min_price,
        'max_price': max_price,
        'delivery_days': delivery_days,
        'sort_by': sort_by,
        'total_count': gigs.count(),
    })


def gig_detail_view(request, gig_id):
    gig = get_object_or_404(Gig.objects.select_related('freelancer', 'category'), id=gig_id)
    packages = gig.packages.all().order_by('price')
    packages_by_tier = {p.tier: p for p in packages}
    
    basic_pkg = packages_by_tier.get(GigPackage.BASIC)
    standard_pkg = packages_by_tier.get(GigPackage.STANDARD)
    premium_pkg = packages_by_tier.get(GigPackage.PREMIUM)

    reviews = Review.objects.filter(gig=gig).select_related('client').order_by('-created_at')
    freelancer_profile = getattr(gig.freelancer, 'freelancer_profile', None)
    other_gigs = Gig.objects.filter(freelancer=gig.freelancer, status=Gig.STATUS_ACTIVE).exclude(id=gig.id)[:3]

    return render(request, 'gigs/detail.html', {
        'gig': gig,
        'packages': packages,
        'basic_pkg': basic_pkg,
        'standard_pkg': standard_pkg,
        'premium_pkg': premium_pkg,
        'reviews': reviews,
        'freelancer_profile': freelancer_profile,
        'other_gigs': other_gigs,
    })


def freelancer_public_profile_view(request, user_id):
    freelancer_user = get_object_or_404(User, id=user_id, role=User.ROLE_FREELANCER)
    profile = get_object_or_404(FreelancerProfile.objects.select_related('user').prefetch_related('skills'), user=freelancer_user)
    portfolios = Portfolio.objects.filter(freelancer=freelancer_user).order_by('-created_at')
    certificates = Certificate.objects.filter(freelancer=freelancer_user).order_by('-issue_date')
    gigs = Gig.objects.filter(freelancer=freelancer_user, status=Gig.STATUS_ACTIVE).prefetch_related('packages')
    reviews = Review.objects.filter(freelancer=freelancer_user).select_related('client', 'gig').order_by('-created_at')

    return render(request, 'freelancer/public_profile.html', {
        'freelancer_user': freelancer_user,
        'profile': profile,
        'portfolios': portfolios,
        'certificates': certificates,
        'gigs': gigs,
        'reviews': reviews,
    })


def category_detail_view(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    gigs = Gig.objects.filter(category=category, status=Gig.STATUS_ACTIVE).select_related('freelancer').prefetch_related('packages')
    
    paginator = Paginator(gigs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'gigs/category_detail.html', {
        'category': category,
        'page_obj': page_obj,
    })


def recommendation_view(request):
    form = RecommendationSearchForm(request.GET or None)
    results_freelancers = []
    results_gigs = []
    has_searched = False

    if form.is_valid():
        has_searched = True
        title = form.cleaned_data.get('title', '')
        description = form.cleaned_data.get('description', '')
        skills_str = form.cleaned_data.get('skills', '')
        budget = form.cleaned_data.get('budget')
        category = form.cleaned_data.get('category')

        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()] if skills_str else []

        results_freelancers = recommend_freelancers(
            project_title=title,
            project_description=description,
            required_skills=skills_list,
            budget=float(budget) if budget else None,
            category=category,
            limit=8
        )

        results_gigs = recommend_gigs(
            project_title=title,
            project_description=description,
            required_skills=skills_list,
            budget=float(budget) if budget else None,
            category=category,
            limit=8
        )

    return render(request, 'recommendations/index.html', {
        'form': form,
        'results_freelancers': results_freelancers,
        'results_gigs': results_gigs,
        'has_searched': has_searched,
    })


# ==========================================
# CLIENT WORKFLOW VIEWS
# ==========================================

@client_required
def client_dashboard_view(request):
    orders = Order.objects.filter(client=request.user).select_related('freelancer', 'gig', 'package').order_by('-created_at')
    
    total_orders = orders.count()
    active_orders = orders.filter(status__in=[Order.STATUS_ACCEPTED, Order.STATUS_IN_PROGRESS, Order.STATUS_SUBMITTED, Order.STATUS_REVISION, Order.STATUS_BACKUP]).count()
    completed_orders = orders.filter(status=Order.STATUS_COMPLETED).count()
    pending_orders = orders.filter(status=Order.STATUS_PENDING).count()

    recent_orders = orders[:6]
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]

    return render(request, 'client/dashboard.html', {
        'total_orders': total_orders,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'pending_orders': pending_orders,
        'recent_orders': recent_orders,
        'notifications': notifications,
    })


@client_required
def client_profile_view(request):
    profile, _ = ClientProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, request.FILES, instance=profile)
        full_name = request.POST.get('full_name', '').strip()
        if form.is_valid():
            if full_name:
                request.user.full_name = full_name
                request.user.save(update_fields=['full_name'])
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('client_profile')
    else:
        form = ClientProfileForm(instance=profile)

    return render(request, 'client/profile.html', {
        'form': form,
        'profile': profile,
    })


@client_required
def client_orders_view(request):
    orders = Order.objects.filter(client=request.user).select_related('freelancer', 'gig', 'package').order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'client/orders.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
    })


@client_required
def place_order_view(request, gig_id, tier):
    gig = get_object_or_404(Gig, id=gig_id, status=Gig.STATUS_ACTIVE)
    package = get_object_or_404(GigPackage, gig=gig, tier=tier)

    if request.method == 'POST':
        requirements = request.POST.get('requirements', '').strip()
        attachment = request.FILES.get('attachment')

        # Prevent ordering own gig
        if gig.freelancer == request.user:
            messages.error(request, "You cannot purchase your own gig service.")
            return redirect('gig_detail', gig_id=gig.id)

        order = Order.objects.create(
            client=request.user,
            freelancer=gig.freelancer,
            gig=gig,
            package=package,
            price=package.price,
            requirements=requirements,
            attachment=attachment,
            status=Order.STATUS_PENDING,
        )

        add_project_history(
            order=order,
            action="Order Created",
            description=f"Client {request.user.username} placed order {order.order_id} for package '{package.name}' (₹{order.price}).",
            performed_by=request.user
        )

        create_notification(
            user=gig.freelancer,
            title="New Order Received",
            message=f"You received a new order {order.order_id} from {request.user.username} for {gig.title}.",
            link=f"/freelancer/orders/{order.id}/"
        )

        messages.success(request, f"Order {order.order_id} created successfully! Please complete the simulated payment to proceed.")
        return redirect('simulated_payment', order_id=order.id)


    return render(request, 'gigs/order_confirm.html', {
        'gig': gig,
        'package': package,
    })


@client_required
def simulated_payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, client=request.user)
    
    payment, created = Payment.objects.get_or_create(
        order=order,
        defaults={
            'client': request.user,
            'freelancer': order.freelancer,
            'amount': order.price,
            'status': Payment.STATUS_PENDING,
        }
    )
    
    if payment.status == Payment.STATUS_PAID:
        messages.info(request, "This order is already paid.")
        return redirect('client_order_detail', order_id=order.id)

    if order.is_overdue():
        messages.error(request, "Time has finished. Please start a new gig to proceed.")
        return redirect('client_order_detail', order_id=order.id)

    # Initialize Razorpay Client
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    amount_in_paise = int(order.price * 100)
    
    if not payment.razorpay_order_id:
        if settings.RAZORPAY_KEY_ID == 'rzp_test_placeholder_key':
            import uuid
            payment.razorpay_order_id = f"sim_order_{uuid.uuid4().hex[:10]}"
            payment.save(update_fields=['razorpay_order_id'])
        else:
            # Create Razorpay Order
            payment_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"receipt_order_{order.id}",
                "payment_capture": 1 # Auto-capture payment
            }
            try:
                razorpay_order = client.order.create(data=payment_data)
                payment.razorpay_order_id = razorpay_order['id']
                payment.save(update_fields=['razorpay_order_id'])
            except Exception as e:
                messages.error(request, f"Failed to initialize payment gateway. Error: {str(e)}")
                return redirect('client_order_detail', order_id=order.id)

    return render(request, 'client/payment_simulate.html', {
        'order': order,
        'payment': payment,
        'razorpay_order_id': payment.razorpay_order_id,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount': amount_in_paise,
    })


@csrf_exempt
def payment_verify_view(request):
    if request.method == "POST":
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        try:
            payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
            order = payment.order
        except Payment.DoesNotExist:
            messages.error(request, "Payment record not found.")
            return redirect('client_dashboard')

        if settings.RAZORPAY_KEY_ID != 'rzp_test_placeholder_key':
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            try:
                client.utility.verify_payment_signature({
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature
                })
            except Exception as e:
                messages.error(request, f"Payment verification error: {str(e)}")
                return redirect('client_order_detail', order_id=order.id)
            
        # Signature is valid (or simulated). Mark order as paid.
        payment.status = Payment.STATUS_PAID
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.paid_at = timezone.now()
        payment.save()
        
        if order.status == Order.STATUS_PENDING:
            order.status = Order.STATUS_ACCEPTED
            order.save(update_fields=['status', 'updated_at'])

        add_project_history(
            order=order,
            action="Payment Completed",
            description=f"Payment of ₹{payment.amount} securely completed via Razorpay.",
            performed_by=payment.client
        )

        create_notification(
            user=order.freelancer,
            title="Payment Verified",
            message=f"Escrow payment of ₹{payment.amount} confirmed for order {order.order_id}. Project is now active.",
            link=f"/freelancer/orders/{order.id}/"
        )

        messages.success(request, "Payment Successful! Your funds are securely in escrow.")
        return redirect('client_order_detail', order_id=order.id)
            
    return redirect('client_dashboard')


@client_required
def client_order_detail_view(request, order_id):
    order = get_object_or_404(Order.objects.select_related('freelancer', 'gig', 'package'), id=order_id, client=request.user)
    deliveries = Delivery.objects.filter(order=order).order_by('-submitted_at')
    revisions = Revision.objects.filter(order=order).order_by('-created_at')
    history = ProjectHistory.objects.filter(order=order).order_by('-created_at')
    review = getattr(order, 'review', None)
    payment = getattr(order, 'payment', None)
    penalty = getattr(order, 'penalty', None)
    backup = order.backup_assignments.filter(status=BackupAssignment.STATUS_ACCEPTED).first()

    revision_form = RevisionForm()
    review_form = ReviewForm()

    return render(request, 'client/order_detail.html', {
        'order': order,
        'deliveries': deliveries,
        'revisions': revisions,
        'history': history,
        'review': review,
        'payment': payment,
        'penalty': penalty,
        'backup': backup,
        'revision_form': revision_form,
        'review_form': review_form,
    })


@client_required
def submit_order_requirements_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, client=request.user)
    if request.method == 'POST':
        form = OrderRequirementForm(request.POST, request.FILES)
        if form.is_valid():
            order.requirements = form.cleaned_data['requirements']
            if form.cleaned_data.get('attachment'):
                order.attachment = form.cleaned_data['attachment']
            order.save()

            add_project_history(
                order=order,
                action="Requirements Submitted",
                description="Client submitted project requirements and specifications.",
                performed_by=request.user
            )

            create_notification(
                user=order.freelancer,
                title="Requirements Submitted",
                message=f"Client submitted requirements for order {order.order_id}.",
                link=f"/freelancer/orders/{order.id}/"
            )

            messages.success(request, "Project requirements updated.")
            return redirect('client_order_detail', order_id=order.id)
    return redirect('client_order_detail', order_id=order.id)


@client_required
def approve_delivery_view(request, order_id, delivery_id):
    order = get_object_or_404(Order, id=order_id, client=request.user)
    delivery = get_object_or_404(Delivery, id=delivery_id, order=order)

    delivery.status = Delivery.STATUS_APPROVED
    delivery.save()

    order.status = Order.STATUS_COMPLETED
    order.completed_at = timezone.now()
    order.save()

    add_project_history(
        order=order,
        action="Delivery Approved",
        description=f"Client approved final delivery submitted by {delivery.freelancer.username}.",
        performed_by=request.user
    )
    add_project_history(
        order=order,
        action="Project Completed",
        description=f"Order {order.order_id} successfully finished and marked completed.",
        performed_by=request.user
    )

    create_notification(
        user=delivery.freelancer,
        title="Delivery Approved - Project Completed",
        message=f"Congratulations! Your delivery for {order.order_id} was approved by {request.user.username}.",
        link=f"/freelancer/orders/{order.id}/"
    )

    messages.success(request, "Delivery approved! The order has been marked as Completed. Please take a moment to leave a review.")
    return redirect('client_order_detail', order_id=order.id)


@client_required
def request_revision_view(request, order_id, delivery_id):
    order = get_object_or_404(Order, id=order_id, client=request.user)
    delivery = get_object_or_404(Delivery, id=delivery_id, order=order)

    if request.method != 'POST':
        return redirect('client_order_detail', order_id=order.id)

    # A pending paid-revision request must be settled before creating another one.
    pending_charge = RevisionCharge.objects.filter(
        revision__order=order, status=RevisionCharge.STATUS_PENDING
    ).first()
    if pending_charge:
        messages.info(request, "Please complete the pending ₹50 revision payment before requesting another revision.")
        return redirect('pay_revision_charge', charge_id=pending_charge.id)

    allowed_revisions = order.package.revisions
    current_revisions_count = order.revisions.count()
    form = RevisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please provide the changes required for this revision.")
        return redirect('client_order_detail', order_id=order.id)

    revision = form.save(commit=False)
    revision.order = order
    revision.client = request.user
    revision.save()

    # Unlimited packages retain their existing behaviour. Every revision after a
    # finite package allowance costs ₹50 and is activated only after payment.
    if allowed_revisions != -1 and current_revisions_count >= allowed_revisions:
        charge = RevisionCharge.objects.create(revision=revision, amount=50)
        add_project_history(order, "Extra Revision Awaiting Payment", f"Revision #{current_revisions_count + 1} requires a ₹50 payment.", request.user)
        messages.info(request, "Your package revision limit has been used. Pay ₹50 to submit this extra revision.")
        return redirect('pay_revision_charge', charge_id=charge.id)

    _activate_revision(order, delivery, revision)
    messages.info(request, "Revision request submitted to freelancer.")
    return redirect('client_order_detail', order_id=order.id)


def _activate_revision(order, delivery, revision):
    """Make a free or paid revision visible to the freelancer."""
    delivery.status = Delivery.STATUS_REVISION
    delivery.save(update_fields=['status'])
    order.status = Order.STATUS_REVISION
    order.save(update_fields=['status', 'updated_at'])
    add_project_history(order, "Revision Requested", f"Client requested revision #{order.revisions.count()}: {revision.reason}", revision.client)
    create_notification(
        user=delivery.freelancer,
        title="Revision Requested",
        message=f"Client {revision.client.username} requested a revision on order {order.order_id}.",
        link=f"/freelancer/orders/{order.id}/"
    )


@client_required
def pay_revision_charge_view(request, charge_id):
    charge = get_object_or_404(RevisionCharge.objects.select_related('revision__order', 'revision__client'), id=charge_id, revision__client=request.user)
    if request.method == 'POST' and charge.status != RevisionCharge.STATUS_PAID:
        charge.status = RevisionCharge.STATUS_PAID
        charge.paid_at = timezone.now()
        charge.save(update_fields=['status', 'paid_at'])
        delivery = charge.revision.order.deliveries.filter(status=Delivery.STATUS_SUBMITTED).order_by('-submitted_at').first()
        if delivery:
            _activate_revision(charge.revision.order, delivery, charge.revision)
        add_project_history(charge.revision.order, "Extra Revision Payment Completed", f"₹{charge.amount} paid for revision #{charge.revision.order.revisions.count()}.", request.user)
        messages.success(request, "₹50 revision payment successful. Your revision request has been sent to the freelancer.")
        return redirect('client_order_detail', order_id=charge.revision.order.id)
    return render(request, 'client/revision_payment.html', {'charge': charge, 'order': charge.revision.order})


@client_required
def create_review_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, client=request.user)
    
    if order.status != Order.STATUS_COMPLETED:
        messages.error(request, "You can only review a completed project.")
        return redirect('client_order_detail', order_id=order.id)

    if hasattr(order, 'review'):
        messages.warning(request, "You have already submitted a review for this order.")
        return redirect('client_order_detail', order_id=order.id)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.order = order
            review.client = request.user
            review.freelancer = order.freelancer
            review.gig = order.gig
            review.save()

            add_project_history(
                order=order,
                action="Review Submitted",
                description=f"Client rated freelancer {review.rating}/5 stars.",
                performed_by=request.user
            )

            create_notification(
                user=order.freelancer,
                title="New Client Review",
                message=f"Client {request.user.username} left you a {review.rating}-star review for order {order.order_id}.",
                link=f"/freelancers/{order.freelancer.id}/"
            )

            messages.success(request, "Thank you! Your review and rating have been recorded.")
            return redirect('client_order_detail', order_id=order.id)

    return redirect('client_order_detail', order_id=order.id)


@client_required
def client_payments_view(request):
    payments = Payment.objects.filter(client=request.user).select_related('order', 'freelancer').order_by('-created_at')
    return render(request, 'client/payments.html', {'payments': payments})


@client_required
def client_reviews_view(request):
    reviews = Review.objects.filter(client=request.user).select_related('order', 'freelancer', 'gig').order_by('-created_at')
    return render(request, 'client/reviews.html', {'reviews': reviews})


# ==========================================
# FREELANCER WORKFLOW VIEWS
# ==========================================

@freelancer_required
def freelancer_dashboard_view(request):
    earnings = calculate_freelancer_earnings(request.user)
    gigs_count = Gig.objects.filter(freelancer=request.user, status=Gig.STATUS_ACTIVE).count()
    
    orders = Order.objects.filter(freelancer=request.user).select_related('client', 'gig', 'package').order_by('-created_at')
    active_orders = orders.filter(status__in=[Order.STATUS_ACCEPTED, Order.STATUS_IN_PROGRESS, Order.STATUS_SUBMITTED, Order.STATUS_REVISION]).count()
    completed_orders = orders.filter(status=Order.STATUS_COMPLETED).count()
    delayed_orders = orders.filter(status=Order.STATUS_DELAYED).count()

    recent_orders = orders[:6]
    
    backup_count = BackupAssignment.objects.filter(
        backup_freelancer=request.user, status=BackupAssignment.STATUS_ASSIGNED
    ).count()

    profile = getattr(request.user, 'freelancer_profile', None)
    verification = getattr(request.user, 'verification', None)

    return render(request, 'freelancer/dashboard.html', {
        'earnings': earnings,
        'gigs_count': gigs_count,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'delayed_orders': delayed_orders,
        'recent_orders': recent_orders,
        'backup_count': backup_count,
        'profile': profile,
        'verification': verification,
    })


@freelancer_required
def freelancer_profile_view(request):
    profile, _ = FreelancerProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = FreelancerProfileForm(request.POST, request.FILES, instance=profile)
        full_name = request.POST.get('full_name', '').strip()
        if form.is_valid():
            if full_name:
                request.user.full_name = full_name
                request.user.save(update_fields=['full_name'])
            form.save()
            messages.success(request, "Freelancer profile updated successfully.")
            return redirect('freelancer_profile')
    else:
        form = FreelancerProfileForm(instance=profile)

    return render(request, 'freelancer/profile.html', {
        'form': form,
        'profile': profile,
    })


@freelancer_required
def freelancer_portfolio_view(request):
    portfolios = Portfolio.objects.filter(freelancer=request.user).order_by('-created_at')
    if request.method == 'POST':
        form = PortfolioForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.freelancer = request.user
            item.save()
            messages.success(request, "Portfolio item added.")
            return redirect('freelancer_portfolio')
    else:
        form = PortfolioForm()

    return render(request, 'freelancer/portfolio.html', {
        'portfolios': portfolios,
        'form': form,
    })


@freelancer_required
def delete_portfolio_view(request, item_id):
    item = get_object_or_404(Portfolio, id=item_id, freelancer=request.user)
    item.delete()
    messages.success(request, "Portfolio item removed.")
    return redirect('freelancer_portfolio')


@freelancer_required
def freelancer_certificates_view(request):
    certificates = Certificate.objects.filter(freelancer=request.user).order_by('-issue_date')
    if request.method == 'POST':
        form = CertificateForm(request.POST, request.FILES)
        if form.is_valid():
            cert = form.save(commit=False)
            cert.freelancer = request.user
            cert.save()
            messages.success(request, "Certificate added successfully.")
            return redirect('freelancer_certificates')
    else:
        form = CertificateForm()

    return render(request, 'freelancer/certificates.html', {
        'certificates': certificates,
        'form': form,
    })


@freelancer_required
def delete_certificate_view(request, cert_id):
    cert = get_object_or_404(Certificate, id=cert_id, freelancer=request.user)
    cert.delete()
    messages.success(request, "Certificate removed.")
    return redirect('freelancer_certificates')


@freelancer_required
def freelancer_gigs_view(request):
    gigs = Gig.objects.filter(freelancer=request.user).prefetch_related('packages').order_by('-created_at')
    return render(request, 'freelancer/gigs.html', {'gigs': gigs})


@freelancer_required
def freelancer_gig_create_view(request):
    verification = getattr(request.user, 'verification', None)
    if not verification or verification.status != FreelancerVerification.STATUS_APPROVED:
        messages.warning(request, "Complete and pass freelancer identity verification before publishing a gig.")
        return redirect('freelancer_verification')
    if request.method == 'POST':
        gig_form = GigForm(request.POST, request.FILES)
        if gig_form.is_valid():
            gig = gig_form.save(commit=False)
            gig.freelancer = request.user
            gig.save()

            # Create packages from POST data
            tiers = [
                (GigPackage.BASIC, 'Basic', request.POST.get('basic_price'), request.POST.get('basic_days'), request.POST.get('basic_revisions', 1), request.POST.get('basic_desc', 'Basic Package'), request.POST.get('basic_features', '')),
                (GigPackage.STANDARD, 'Standard', request.POST.get('std_price'), request.POST.get('std_days'), request.POST.get('std_revisions', 3), request.POST.get('std_desc', 'Standard Package'), request.POST.get('std_features', '')),
                (GigPackage.PREMIUM, 'Premium', request.POST.get('prem_price'), request.POST.get('prem_days'), request.POST.get('prem_revisions', -1), request.POST.get('prem_desc', 'Premium Package'), request.POST.get('prem_features', '')),
            ]

            for tier, name, price, days, revs, desc, feats in tiers:
                if price and days:
                    GigPackage.objects.create(
                        gig=gig,
                        tier=tier,
                        name=name,
                        price=float(price),
                        delivery_days=int(days),
                        revisions=int(revs) if revs else 1,
                        description=desc or f"{name} Tier Service",
                        features=feats or ''
                    )

            messages.success(request, f"Gig '{gig.title}' created successfully!")
            return redirect('freelancer_gigs')
    else:
        gig_form = GigForm()

    return render(request, 'freelancer/gig_form.html', {'gig_form': gig_form, 'is_edit': False})


@freelancer_required
def freelancer_verification_view(request):
    import base64
    from django.core.files.base import ContentFile
    
    verification = getattr(request.user, 'verification', None)
    if request.method == 'POST':
        form = FreelancerVerificationForm(request.POST, request.FILES, instance=verification)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.user = request.user
            
            # Process selfie data
            selfie_data = form.cleaned_data['selfie_data']
            format, imgstr = selfie_data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'selfie_{request.user.id}.{ext}')
            verification.selfie_image = data
            
            verification.status = FreelancerVerification.STATUS_PENDING
            verification.liveness_status = FreelancerVerification.STATUS_PENDING
            verification.reviewed_at = None
            verification.save()
            messages.success(request, 'Verification documents and live photo submitted successfully. Pending manual review.')
            return redirect('freelancer_verification')
    else:
        form = FreelancerVerificationForm(instance=verification)
    return render(request, 'freelancer/verification.html', {'form': form, 'verification': verification})


@freelancer_required
def freelancer_gig_edit_view(request, gig_id):
    gig = get_object_or_404(Gig, id=gig_id, freelancer=request.user)
    packages = {p.tier: p for p in gig.packages.all()}

    if request.method == 'POST':
        gig_form = GigForm(request.POST, request.FILES, instance=gig)
        if gig_form.is_valid():
            gig_form.save()

            # Update or create package tiers
            tiers = [
                (GigPackage.BASIC, 'Basic', request.POST.get('basic_price'), request.POST.get('basic_days'), request.POST.get('basic_revisions', 1), request.POST.get('basic_desc', 'Basic Package'), request.POST.get('basic_features', '')),
                (GigPackage.STANDARD, 'Standard', request.POST.get('std_price'), request.POST.get('std_days'), request.POST.get('std_revisions', 3), request.POST.get('std_desc', 'Standard Package'), request.POST.get('std_features', '')),
                (GigPackage.PREMIUM, 'Premium', request.POST.get('prem_price'), request.POST.get('prem_days'), request.POST.get('prem_revisions', -1), request.POST.get('prem_desc', 'Premium Package'), request.POST.get('prem_features', '')),
            ]

            for tier, name, price, days, revs, desc, feats in tiers:
                if price and days:
                    pkg = packages.get(tier)
                    if pkg:
                        pkg.name = name
                        pkg.price = float(price)
                        pkg.delivery_days = int(days)
                        pkg.revisions = int(revs) if revs else 1
                        pkg.description = desc
                        pkg.features = feats
                        pkg.save()
                    else:
                        GigPackage.objects.create(
                            gig=gig,
                            tier=tier,
                            name=name,
                            price=float(price),
                            delivery_days=int(days),
                            revisions=int(revs) if revs else 1,
                            description=desc,
                            features=feats
                        )

            messages.success(request, f"Gig '{gig.title}' updated successfully.")
            return redirect('freelancer_gigs')
    else:
        gig_form = GigForm(instance=gig)

    return render(request, 'freelancer/gig_form.html', {
        'gig_form': gig_form,
        'gig': gig,
        'basic_pkg': packages.get(GigPackage.BASIC),
        'std_pkg': packages.get(GigPackage.STANDARD),
        'prem_pkg': packages.get(GigPackage.PREMIUM),
        'is_edit': True,
    })


@freelancer_required
def freelancer_gig_toggle_view(request, gig_id):
    gig = get_object_or_404(Gig, id=gig_id, freelancer=request.user)
    gig.status = Gig.STATUS_INACTIVE if gig.status == Gig.STATUS_ACTIVE else Gig.STATUS_ACTIVE
    gig.save()
    status_str = "activated" if gig.status == Gig.STATUS_ACTIVE else "deactivated"
    messages.info(request, f"Gig '{gig.title}' {status_str}.")
    return redirect('freelancer_gigs')


@freelancer_required
def freelancer_orders_view(request):
    orders = Order.objects.filter(freelancer=request.user).select_related('client', 'gig', 'package').order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'freelancer/orders.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
    })


@freelancer_required
def freelancer_order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('client', 'gig', 'package'),
        id=order_id
    )
    # Check if primary or accepted backup freelancer
    is_backup = BackupAssignment.objects.filter(order=order, backup_freelancer=request.user, status=BackupAssignment.STATUS_ACCEPTED).exists()
    if order.freelancer != request.user and not is_backup:
        raise HttpResponseForbidden("You are not authorized to view this order.")

    deliveries = Delivery.objects.filter(order=order).order_by('-submitted_at')
    revisions = Revision.objects.filter(order=order).order_by('-created_at')
    history = ProjectHistory.objects.filter(order=order).order_by('-created_at')
    delivery_form = DeliveryForm()
    penalty = getattr(order, 'penalty', None)

    return render(request, 'freelancer/order_detail.html', {
        'order': order,
        'deliveries': deliveries,
        'revisions': revisions,
        'history': history,
        'delivery_form': delivery_form,
        'penalty': penalty,
        'is_backup': is_backup,
    })


@freelancer_required
def freelancer_order_respond_view(request, order_id, action):
    order = get_object_or_404(Order, id=order_id, freelancer=request.user)
    
    if action == 'accept':
        order.status = Order.STATUS_IN_PROGRESS
        order.save(update_fields=['status', 'updated_at'])

        add_project_history(
            order=order,
            action="Order Accepted",
            description=f"Freelancer {request.user.username} accepted order. Project is now In Progress.",
            performed_by=request.user
        )

        create_notification(
            user=order.client,
            title="Order Accepted",
            message=f"Freelancer {request.user.username} accepted your order {order.order_id}.",
            link=f"/client/orders/{order.id}/"
        )
        messages.success(request, f"Order {order.order_id} accepted! Project is now in progress.")

    elif action == 'reject':
        order.status = Order.STATUS_REJECTED
        order.save(update_fields=['status', 'updated_at'])

        add_project_history(
            order=order,
            action="Order Rejected",
            description=f"Freelancer {request.user.username} declined order.",
            performed_by=request.user
        )

        create_notification(
            user=order.client,
            title="Order Declined",
            message=f"Freelancer {request.user.username} was unable to accept order {order.order_id}.",
            link=f"/client/orders/{order.id}/"
        )
        messages.warning(request, f"Order {order.order_id} rejected.")

    return redirect('freelancer_order_detail', order_id=order.id)


@freelancer_required
def freelancer_delivery_submit_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    is_backup = BackupAssignment.objects.filter(order=order, backup_freelancer=request.user, status=BackupAssignment.STATUS_ACCEPTED).exists()
    if order.freelancer != request.user and not is_backup:
        raise HttpResponseForbidden("Access denied.")

    if request.method == 'POST':
        form = DeliveryForm(request.POST, request.FILES)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.order = order
            delivery.freelancer = request.user
            delivery.status = Delivery.STATUS_SUBMITTED
            delivery.save()

            order.status = Order.STATUS_SUBMITTED
            order.save()

            add_project_history(
                order=order,
                action="Delivery Submitted",
                description=f"Freelancer {request.user.username} submitted completed work delivery.",
                performed_by=request.user
            )

            create_notification(
                user=order.client,
                title="Delivery Submitted",
                message=f"Freelancer {request.user.username} submitted delivery for order {order.order_id}. Please review.",
                link=f"/client/orders/{order.id}/"
            )

            messages.success(request, "Delivery submitted to client for approval!")
            return redirect('freelancer_order_detail', order_id=order.id)

    return redirect('freelancer_order_detail', order_id=order.id)


@freelancer_required
def freelancer_earnings_view(request):
    earnings = calculate_freelancer_earnings(request.user)
    payments = Payment.objects.filter(freelancer=request.user).select_related('order', 'client').order_by('-created_at')
    revision_charges = RevisionCharge.objects.filter(
        revision__order__freelancer=request.user, status=RevisionCharge.STATUS_PAID
    ).select_related('revision__order', 'revision__client').order_by('-paid_at')
    penalties = Penalty.objects.filter(freelancer=request.user).select_related('order').order_by('-created_at')

    return render(request, 'freelancer/earnings.html', {
        'earnings': earnings,
        'payments': payments,
        'revision_charges': revision_charges,
        'penalties': penalties,
    })


@freelancer_required
def freelancer_backup_assignments_view(request):
    assignments = BackupAssignment.objects.filter(
        backup_freelancer=request.user
    ).select_related('order', 'primary_freelancer', 'assigned_by').order_by('-assigned_at')

    return render(request, 'freelancer/backup_assignments.html', {
        'assignments': assignments,
    })


@freelancer_required
def freelancer_backup_respond_view(request, assignment_id, action):
    assignment = get_object_or_404(BackupAssignment, id=assignment_id, backup_freelancer=request.user)

    if action == 'accept':
        assignment.status = BackupAssignment.STATUS_ACCEPTED
        assignment.accepted_at = timezone.now()
        assignment.save()

        # Update order status to Backup Assigned and link new active handler
        order = assignment.order
        order.status = Order.STATUS_BACKUP
        order.freelancer = request.user
        order.save(update_fields=['status', 'freelancer', 'updated_at'])

        add_project_history(
            order=order,
            action="Backup Accepted",
            description=f"Backup freelancer {request.user.username} accepted project assignment. Continuing delivery.",
            performed_by=request.user
        )

        create_notification(
            user=order.client,
            title="Backup Assignment Accepted",
            message=f"Backup freelancer {request.user.username} accepted your project {order.order_id} and resumed work.",
            link=f"/client/orders/{order.id}/"
        )

        messages.success(request, f"Backup assignment for order {order.order_id} accepted! You can now manage this project.")
        return redirect('freelancer_order_detail', order_id=order.id)


    elif action == 'reject':
        assignment.status = BackupAssignment.STATUS_REJECTED
        assignment.save()

        add_project_history(
            order=assignment.order,
            action="Backup Assignment Rejected",
            description=f"Backup freelancer {request.user.username} declined assignment.",
            performed_by=request.user
        )

        # Notify Admin
        create_notification(
            user=assignment.assigned_by,
            title="Backup Assignment Declined",
            message=f"Freelancer {request.user.username} declined backup assignment for {assignment.order.order_id}. Please reassign.",
            link=f"/admin-dashboard/orders/{assignment.order.id}/assign-backup/"
        )

        messages.info(request, "Backup assignment declined.")
        return redirect('freelancer_backup_assignments')


# ==========================================
# ADMINISTRATOR WORKFLOW VIEWS
# ==========================================

@admin_required
def admin_dashboard_view(request):
    # Run automatic delay detection when admin opens dashboard
    check_and_apply_delays()

    stats = {
        'total_users': User.objects.count(),
        'total_clients': User.objects.filter(role=User.ROLE_CLIENT).count(),
        'total_freelancers': User.objects.filter(role=User.ROLE_FREELANCER).count(),
        'total_gigs': Gig.objects.count(),
        'total_orders': Order.objects.count(),
        'active_orders': Order.objects.filter(status__in=[Order.STATUS_ACCEPTED, Order.STATUS_IN_PROGRESS, Order.STATUS_SUBMITTED, Order.STATUS_REVISION, Order.STATUS_BACKUP]).count(),
        'completed_orders': Order.objects.filter(status=Order.STATUS_COMPLETED).count(),
        'delayed_orders': Order.objects.filter(status=Order.STATUS_DELAYED, backup_assignments__isnull=True).count(),
        'total_payments': Payment.objects.filter(status=Payment.STATUS_PAID).aggregate(s=Sum('amount'))['s'] or 0,
        'total_penalties': Penalty.objects.filter(status=Penalty.STATUS_APPLIED).aggregate(s=Sum('penalty_amount'))['s'] or 0,
        'backup_assignments': BackupAssignment.objects.count(),
    }

    recent_orders = Order.objects.select_related('client', 'freelancer', 'gig').order_by('-created_at')[:6]
    delayed_projects = Order.objects.filter(status=Order.STATUS_DELAYED).select_related('client', 'freelancer', 'gig')[:5]
    recent_users = User.objects.exclude(role=User.ROLE_ADMIN).exclude(is_superuser=True).exclude(is_staff=True).order_by('-date_joined')[:6]
    recent_payments = Payment.objects.select_related('client', 'freelancer', 'order').order_by('-created_at')[:5]

    return render(request, 'administrator/dashboard.html', {
        'stats': stats,
        'recent_orders': recent_orders,
        'delayed_projects': delayed_projects,
        'recent_users': recent_users,
        'recent_payments': recent_payments,
    })


@admin_required
def admin_users_view(request):
    users = User.objects.exclude(role=User.ROLE_ADMIN).exclude(is_superuser=True).exclude(is_staff=True).order_by('-date_joined')
    role_filter = request.GET.get('role')
    query = request.GET.get('q', '').strip()

    if role_filter:
        users = users.filter(role=role_filter)
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(full_name__icontains=query)
        )

    paginator = Paginator(users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'administrator/users.html', {
        'page_obj': page_obj,
        'role_filter': role_filter,
        'query': query,
    })


@admin_required
def admin_user_toggle_active_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own administrator account.")
        return redirect('admin_users')

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])
    status_str = "activated" if target_user.is_active else "deactivated"
    messages.info(request, f"User {target_user.username} {status_str}.")
    return redirect('admin_users')


@admin_required
def admin_clients_view(request):
    clients = User.objects.filter(role=User.ROLE_CLIENT).select_related('client_profile').order_by('-date_joined')
    paginator = Paginator(clients, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'administrator/clients.html', {'page_obj': page_obj})


@admin_required
def admin_freelancers_view(request):
    freelancers = User.objects.filter(role=User.ROLE_FREELANCER).select_related('freelancer_profile', 'verification').order_by('-date_joined')
    paginator = Paginator(freelancers, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'administrator/freelancers.html', {'page_obj': page_obj})


@admin_required
def admin_verifications_view(request):
    verifications = FreelancerVerification.objects.select_related('user').order_by('status', '-submitted_at')
    return render(request, 'administrator/verifications.html', {'verifications': verifications})


@admin_required
def admin_verification_review_view(request, verification_id, action):
    verification = get_object_or_404(FreelancerVerification, id=verification_id)
    if request.method != 'POST' or action not in ['approve', 'reject']:
        return redirect('admin_verifications')
    verification.status = FreelancerVerification.STATUS_APPROVED if action == 'approve' else FreelancerVerification.STATUS_REJECTED
    verification.liveness_status = verification.status
    verification.reviewer_notes = request.POST.get('reviewer_notes', '').strip()
    verification.reviewed_at = timezone.now()
    verification.save(update_fields=['status', 'liveness_status', 'reviewer_notes', 'reviewed_at'])
    messages.success(request, f"Verification for {verification.user.username} {action}d.")
    return redirect('admin_verifications')


@admin_required
def admin_verification_file_view(request, verification_id, file_type):
    """Serve sensitive KYC uploads only to an authenticated administrator."""
    verification = get_object_or_404(FreelancerVerification, id=verification_id)
    if file_type == 'document':
        uploaded_file = verification.document_file
    elif file_type == 'selfie':
        uploaded_file = verification.selfie_image
    else:
        return HttpResponseForbidden('Unknown verification file.')
    return FileResponse(uploaded_file.open('rb'), as_attachment=False)


@admin_required
def admin_gigs_view(request):
    gigs = Gig.objects.select_related('freelancer', 'category').order_by('-created_at')
    status_filter = request.GET.get('status')
    query = request.GET.get('q', '').strip()

    if status_filter:
        gigs = gigs.filter(status=status_filter)
    if query:
        gigs = gigs.filter(
            Q(title__icontains=query) |
            Q(freelancer__username__icontains=query)
        )

    paginator = Paginator(gigs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'administrator/gigs.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'query': query,
    })


@admin_required
def admin_gig_toggle_view(request, gig_id):
    gig = get_object_or_404(Gig, id=gig_id)
    gig.status = Gig.STATUS_INACTIVE if gig.status == Gig.STATUS_ACTIVE else Gig.STATUS_ACTIVE
    gig.save(update_fields=['status'])
    status_str = "activated" if gig.status == Gig.STATUS_ACTIVE else "deactivated"
    messages.info(request, f"Gig '{gig.title}' {status_str}.")
    return redirect('admin_gigs')


@admin_required
def admin_orders_view(request):
    orders = Order.objects.select_related('client', 'freelancer', 'gig', 'package').order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'administrator/orders.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
    })


@admin_required
def admin_order_detail_view(request, order_id):
    order = get_object_or_404(Order.objects.select_related('client', 'freelancer', 'gig', 'package'), id=order_id)
    deliveries = Delivery.objects.filter(order=order).order_by('-submitted_at')
    revisions = Revision.objects.filter(order=order).order_by('-created_at')
    history = ProjectHistory.objects.filter(order=order).order_by('-created_at')
    payment = getattr(order, 'payment', None)
    penalty = getattr(order, 'penalty', None)
    backup_assignments = order.backup_assignments.all().order_by('-assigned_at')

    return render(request, 'administrator/order_detail.html', {
        'order': order,
        'deliveries': deliveries,
        'revisions': revisions,
        'history': history,
        'payment': payment,
        'penalty': penalty,
        'backup_assignments': backup_assignments,
    })


@admin_required
def admin_delayed_projects_view(request):
    # Run delay checker
    check_and_apply_delays()
    delayed_orders = Order.objects.filter(status=Order.STATUS_DELAYED).select_related('client', 'freelancer', 'gig', 'package').order_by('-deadline')
    
    return render(request, 'administrator/delayed_projects.html', {
        'delayed_orders': delayed_orders,
    })


@admin_required
def admin_assign_backup_view(request, order_id):
    order = get_object_or_404(Order.objects.select_related('client', 'freelancer', 'gig'), id=order_id)

    # Get available freelancers excluding primary
    eligible_freelancers = User.objects.filter(
        role=User.ROLE_FREELANCER,
        is_active=True
    ).exclude(id=order.freelancer.id).select_related('freelancer_profile').prefetch_related('freelancer_profile__skills')

    # Recommendation scoring for backup candidates
    gig_tags = [t.lower().strip() for t in order.gig.tags_list()]
    candidate_list = []
    for cand in eligible_freelancers:
        prof = getattr(cand, 'freelancer_profile', None)
        skills = [s.name.lower() for s in prof.skills.all()] if prof else []
        
        match_count = sum(1 for s in skills if any(s in t or t in s for t in gig_tags))
        match_score = min(99, int(50 + (match_count * 15) + ((prof.avg_rating() if prof else 0) * 8)))

        candidate_list.append({
            'user': cand,
            'profile': prof,
            'skills': [s.name for s in prof.skills.all()] if prof else [],
            'match_score': match_score,
        })
    candidate_list.sort(key=lambda x: x['match_score'], reverse=True)

    if request.method == 'POST':
        backup_user_id = request.POST.get('backup_freelancer')
        reason = request.POST.get('reason', 'Primary freelancer missed deadline. Assigned backup to ensure project continuity.').strip()

        backup_user = get_object_or_404(User, id=backup_user_id, role=User.ROLE_FREELANCER, is_active=True)
        assign_backup_freelancer(
            order=order,
            backup_freelancer=backup_user,
            admin_user=request.user,
            reason=reason
        )

        messages.success(request, f"Backup freelancer {backup_user.username} has been assigned to order {order.order_id}.")
        return redirect('admin_backup_assignments')

    return render(request, 'administrator/assign_backup.html', {
        'order': order,
        'candidates': candidate_list,
    })


@admin_required
def admin_penalties_view(request):
    penalties = Penalty.objects.select_related('order', 'freelancer').order_by('-created_at')
    return render(request, 'administrator/penalties.html', {'penalties': penalties})


@admin_required
def admin_backup_assignments_view(request):
    assignments = BackupAssignment.objects.select_related('order', 'primary_freelancer', 'backup_freelancer', 'assigned_by').order_by('-assigned_at')
    return render(request, 'administrator/backup_assignments.html', {'assignments': assignments})


@admin_required
def admin_payments_view(request):
    payments = Payment.objects.select_related('order', 'client', 'freelancer').order_by('-created_at')
    return render(request, 'administrator/payments.html', {'payments': payments})


@admin_required
def admin_categories_view(request):
    categories = Category.objects.annotate(gigs_count=Count('gigs')).order_by('name')
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully.")
            return redirect('admin_categories')
    else:
        form = CategoryForm()

    return render(request, 'administrator/categories.html', {
        'categories': categories,
        'form': form,
    })


@admin_required
def admin_reviews_view(request):
    reviews = Review.objects.select_related('client', 'freelancer', 'gig', 'order').order_by('-created_at')
    return render(request, 'administrator/reviews.html', {'reviews': reviews})


# ==========================================
# MESSAGING VIEWS
# ==========================================

def _can_message_contact(user, contact):
    """Allow direct messages only between active client and freelancer accounts."""
    if not contact.is_active:
        return False
    return (
        (user.is_client() and contact.is_freelancer())
        or (user.is_freelancer() and contact.is_client())
    )


def _shared_order_for_message(user, contact):
    """Associate a message with the most recent shared order when one exists."""
    if user.is_client():
        return Order.objects.filter(client=user, freelancer=contact).order_by('-created_at').first()
    if user.is_freelancer():
        return Order.objects.filter(client=contact, freelancer=user).order_by('-created_at').first()
    return None

@login_required
def messages_inbox_view(request):
    # Include people the user has messaged and project counterparts from orders.
    # This lets a client or freelancer begin a chat as soon as a gig order exists.
    sent_to = Message.objects.filter(sender=request.user).values_list('receiver_id', flat=True)
    received_from = Message.objects.filter(receiver=request.user).values_list('sender_id', flat=True)
    contact_ids = set(list(sent_to) + list(received_from))

    if request.user.is_client():
        project_contacts = Order.objects.filter(client=request.user).values_list('freelancer_id', flat=True)
    elif request.user.is_freelancer():
        project_contacts = Order.objects.filter(freelancer=request.user).values_list('client_id', flat=True)
    else:
        project_contacts = []
    contact_ids.update(project_contacts)

    contacts = User.objects.filter(id__in=contact_ids)
    conversations = []
    for contact in contacts:
        last_msg = Message.objects.filter(
            (Q(sender=request.user, receiver=contact) | Q(sender=contact, receiver=request.user))
        ).order_by('-created_at').first()
        unread_count = Message.objects.filter(sender=contact, receiver=request.user, is_read=False).count()
        conversations.append({
            'contact': contact,
            'last_message': last_msg,
            'unread_count': unread_count,
        })
    conversations.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else timezone.now(), reverse=True)

    return render(request, 'messages/inbox.html', {'conversations': conversations})


@login_required
def messages_thread_view(request, user_id):
    contact = get_object_or_404(User, id=user_id)
    if contact == request.user:
        return redirect('messages_inbox')
    if not _can_message_contact(request.user, contact):
        messages.error(request, "Direct messages are available only between client and freelancer accounts.")
        return redirect('messages_inbox')

    # Mark received messages from this contact as read
    Message.objects.filter(sender=contact, receiver=request.user, is_read=False).update(is_read=True)

    messages_list = Message.objects.filter(
        (Q(sender=request.user, receiver=contact) | Q(sender=contact, receiver=request.user))
    ).order_by('created_at')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.receiver = contact
            msg.order = _shared_order_for_message(request.user, contact)
            msg.save()

            create_notification(
                user=contact,
                title="New Message",
                message=f"You received a message from {request.user.username}.",
                link=f"/messages/{request.user.id}/"
            )
            return redirect('messages_thread', user_id=contact.id)
    else:
        form = MessageForm()

    return render(request, 'messages/conversation.html', {
        'contact': contact,
        'messages_list': messages_list,
        'form': form,
    })


# ==========================================
# NOTIFICATIONS VIEWS
# ==========================================

@login_required
def notifications_list_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'notifications/list.html', {'notifications': notifications})


@login_required
def notification_mark_read_view(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    if notif.link:
        return redirect(notif.link)
    return redirect('notifications_list')


@login_required
def notifications_mark_all_read_view(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.info(request, "All notifications marked as read.")
    return redirect('notifications_list')


# ==========================================
# ERROR HANDLERS
# ==========================================

def custom_404_view(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def custom_403_view(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def custom_500_view(request):
    return render(request, 'errors/500.html', status=500)

from django.http import JsonResponse
from .services import CashfreeAadhaarService
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def ajax_send_aadhaar_otp(request):
    if request.method == 'POST':
        aadhaar_number = request.POST.get('aadhaar_number')
        if not aadhaar_number or len(aadhaar_number) != 12:
            return JsonResponse({'success': False, 'message': 'Invalid Aadhaar number'})
            
        result = CashfreeAadhaarService.send_otp(aadhaar_number)
        if result.get('success'):
            request.session['aadhaar_ref_id'] = result.get('ref_id')
        return JsonResponse(result)
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@csrf_exempt
def ajax_verify_aadhaar_otp(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        ref_id = request.session.get('aadhaar_ref_id')
        
        if not otp or not ref_id:
            return JsonResponse({'success': False, 'message': 'Missing OTP or Ref ID'})
            
        result = CashfreeAadhaarService.verify_otp(ref_id, otp)
        if result.get('success'):
            request.session['aadhaar_verified'] = True
        return JsonResponse(result)
    return JsonResponse({'success': False, 'message': 'Invalid request'})
