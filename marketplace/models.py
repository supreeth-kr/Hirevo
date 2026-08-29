from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    ROLE_CLIENT = 'client'
    ROLE_FREELANCER = 'freelancer'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_CLIENT, 'Client'),
        (ROLE_FREELANCER, 'Freelancer'),
        (ROLE_ADMIN, 'Administrator'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CLIENT)
    full_name = models.CharField(max_length=200, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)

    def is_client(self):
        return self.role == self.ROLE_CLIENT

    def is_freelancer(self):
        return self.role == self.ROLE_FREELANCER

    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_staff

    def __str__(self):
        return f"{self.username} ({self.role})"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='bi-grid')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class FreelancerProfile(models.Model):
    AVAILABILITY_CHOICES = [
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='freelancer_profile')
    bio = models.TextField(blank=True)
    skills = models.ManyToManyField(Skill, blank=True)
    experience_years = models.IntegerField(default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='available')
    languages = models.CharField(max_length=255, blank=True)
    education = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def avg_rating(self):
        reviews = Review.objects.filter(freelancer=self.user)
        if not reviews.exists():
            return 0
        return round(sum(r.rating for r in reviews) / reviews.count(), 1)

    def total_reviews(self):
        return Review.objects.filter(freelancer=self.user).count()

    def completed_projects(self):
        return Order.objects.filter(freelancer=self.user, status='completed').count()

    def __str__(self):
        return f"{self.user.username}'s Profile"


class FreelancerVerification(models.Model):
    """Private KYC submission. Documents are never displayed on public profiles."""
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending review'),
        (STATUS_APPROVED, 'Verified'),
        (STATUS_REJECTED, 'Rejected'),
    ]
    DOCUMENT_AADHAAR = 'aadhaar'
    DOCUMENT_PAN = 'pan'
    DOCUMENT_PASSPORT = 'passport'
    DOCUMENT_DRIVING_LICENSE = 'driving_license'
    DOCUMENT_CHOICES = [
        (DOCUMENT_AADHAAR, 'Aadhaar card'),
        (DOCUMENT_PAN, 'PAN card'),
        (DOCUMENT_PASSPORT, 'Passport'),
        (DOCUMENT_DRIVING_LICENSE, 'Driving licence'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_CHOICES, blank=True, null=True)
    document_file = models.FileField(upload_to='verification_documents/', blank=True, null=True)
    selfie_image = models.ImageField(upload_to='verification_selfies/', blank=True, null=True)
    liveness_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Verification for {self.user.username} ({self.status})"


class ClientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Client Profile"


class Portfolio(models.Model):
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_items')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='portfolio/', blank=True, null=True)
    project_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Certificate(models.Model):
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    name = models.CharField(max_length=200)
    issuing_organization = models.CharField(max_length=200)
    issue_date = models.DateField()
    description = models.TextField(blank=True)
    certificate_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Gig(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gigs')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='gigs')
    title = models.CharField(max_length=255)
    description = models.TextField()
    tags = models.CharField(max_length=255, blank=True, help_text='Comma separated tags')
    requirements = models.TextField(blank=True)
    faqs = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='gigs/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def avg_rating(self):
        reviews = Review.objects.filter(gig=self)
        if not reviews.exists():
            return 0
        return round(sum(r.rating for r in reviews) / reviews.count(), 1)

    def total_reviews(self):
        return Review.objects.filter(gig=self).count()

    def starting_price(self):
        pkg = self.packages.order_by('price').first()
        return pkg.price if pkg else 0

    def min_delivery(self):
        pkg = self.packages.order_by('delivery_days').first()
        return pkg.delivery_days if pkg else 0

    def tags_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def __str__(self):
        return self.title


class GigPackage(models.Model):
    BASIC = 'basic'
    STANDARD = 'standard'
    PREMIUM = 'premium'
    TIER_CHOICES = [(BASIC, 'Basic'), (STANDARD, 'Standard'), (PREMIUM, 'Premium')]

    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='packages')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_days = models.IntegerField()
    revisions = models.IntegerField(default=1)
    features = models.TextField(blank=True, help_text='Comma separated features')

    class Meta:
        unique_together = ('gig', 'tier')

    def features_list(self):
        return [f.strip() for f in self.features.split(',') if f.strip()]

    def __str__(self):
        return f"{self.gig.title} - {self.tier}"


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SUBMITTED = 'submitted'
    STATUS_REVISION = 'revision_requested'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_DELAYED = 'delayed'
    STATUS_BACKUP = 'backup_assigned'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_REVISION, 'Revision Requested'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_DELAYED, 'Delayed'),
        (STATUS_BACKUP, 'Backup Assigned'),
    ]

    order_id = models.CharField(max_length=20, unique=True, editable=False)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_orders')
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='freelancer_orders')
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='orders')
    package = models.ForeignKey(GigPackage, on_delete=models.CASCADE, related_name='orders')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    requirements = models.TextField(blank=True)
    attachment = models.FileField(upload_to='order_attachments/', blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    deadline = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            count = Order.objects.count() + 1
            self.order_id = f"HV-{timezone.now().year}-{count:05d}"
        if not self.deadline and self.package_id:
            try:
                pkg = GigPackage.objects.get(pk=self.package_id)
                self.deadline = timezone.now() + timezone.timedelta(days=pkg.delivery_days)
            except GigPackage.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def is_overdue(self):
        return (self.deadline and timezone.now() > self.deadline and
                self.status not in ['completed', 'cancelled', 'delayed', 'backup_assigned'])

    def days_delayed(self):
        if self.deadline and timezone.now() > self.deadline:
            return (timezone.now() - self.deadline).days
        return 0

    def revision_count(self):
        return self.revisions.count()

    def __str__(self):
        return self.order_id


class Delivery(models.Model):
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_REVISION = 'revision_requested'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REVISION, 'Revision Requested'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='deliveries')
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deliveries')
    description = models.TextField()
    delivery_file = models.FileField(upload_to='deliveries/', blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Delivery for {self.order.order_id}"


class Revision(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='revisions')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='revisions_requested')
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Revision for {self.order.order_id}"


class RevisionCharge(models.Model):
    """A separate payment record for a revision beyond a package allowance."""
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_PAID, 'Paid')]
    revision = models.OneToOneField(Revision, on_delete=models.CASCADE, related_name='charge')
    amount = models.DecimalField(max_digits=7, decimal_places=2, default=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    transaction_id = models.CharField(max_length=30, unique=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            count = RevisionCharge.objects.count() + 1
            self.transaction_id = f"HV-REV-{timezone.now().year}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transaction_id


class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
    ]
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            count = Payment.objects.count() + 1
            self.transaction_id = f"HV-PAY-{timezone.now().year}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transaction_id


class Review(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.client.username} for {self.order.order_id}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


class Penalty(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPLIED = 'applied'
    STATUS_WAIVED = 'waived'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPLIED, 'Applied'),
        (STATUS_WAIVED, 'Waived'),
    ]
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='penalty')
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='penalties')
    order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(default='Missed project deadline')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        amt = Decimal(str(self.order_amount))
        pct = Decimal(str(self.percentage))
        self.penalty_amount = round((amt * pct) / Decimal('100'), 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Penalty for {self.order.order_id}"


class BackupAssignment(models.Model):
    STATUS_ASSIGNED = 'assigned'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_COMPLETED, 'Completed'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='backup_assignments')
    primary_freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='primary_assignments')
    backup_freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='backup_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_assignments')
    reason = models.TextField(default='Primary freelancer missed deadline')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ASSIGNED)
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Backup: {self.backup_freelancer.username} for {self.order.order_id}"


class ProjectHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=100)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = 'Project Histories'

    def __str__(self):
        return f"{self.order.order_id} - {self.action}"


class EmailVerificationOTP(models.Model):
    PURPOSE_REGISTRATION = 'registration'
    PURPOSE_PASSWORD_RESET = 'password_reset'
    PURPOSE_CHOICES = [
        (PURPOSE_REGISTRATION, 'Registration'),
        (PURPOSE_PASSWORD_RESET, 'Password Reset'),
    ]

    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default=PURPOSE_REGISTRATION)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Verification OTP'
        verbose_name_plural = 'Email Verification OTPs'

    def is_valid(self, code):
        if self.is_verified:
            return False, "This OTP has already been used."
        if timezone.now() > self.expires_at:
            return False, "This OTP has expired. Please request a new code."
        if self.attempts >= 5:
            return False, "Too many failed attempts. Please request a new OTP."
        if self.otp_code != str(code).strip():
            self.attempts += 1
            self.save(update_fields=['attempts'])
            return False, "Invalid OTP code. Please check your email and try again."
        return True, "Valid OTP."

    def __str__(self):
        return f"OTP for {self.email} ({self.purpose}) - {'Verified' if self.is_verified else 'Pending'}"
