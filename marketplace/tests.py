from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core import mail

from .models import (
    User, Category, Skill, FreelancerProfile, ClientProfile,
    Gig, GigPackage, Order, Delivery, Revision, RevisionCharge, Payment,
    Review, Penalty, BackupAssignment, ProjectHistory, Notification, Message,
    EmailVerificationOTP, FreelancerVerification
)

from .services import (
    check_and_apply_delays, assign_backup_freelancer,
    calculate_freelancer_earnings
)
from .ai_recommendation import (
    recommend_freelancers, recommend_gigs, _skill_match_score,
    _experience_score, _rating_score
)

User = get_user_model()


class HirevoComprehensiveTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Category & Skills
        self.category = Category.objects.create(
            name="Programming & Tech",
            slug="programming-tech",
            icon="bi-code-slash"
        )
        self.skill_python = Skill.objects.create(name="Python")
        self.skill_django = Skill.objects.create(name="Django")
        self.skill_react = Skill.objects.create(name="React")

        # Create Client User
        self.client_user = User.objects.create_user(
            username="testclient",
            email="client@example.com",
            password="StrongPassword123!",
            role=User.ROLE_CLIENT,
            full_name="Alice Client"
        )
        self.client_profile = ClientProfile.objects.create(
            user=self.client_user,
            location="San Francisco, USA"
        )

        # Create Primary Freelancer User
        self.freelancer_user = User.objects.create_user(
            username="testfreelancer",
            email="freelancer@example.com",
            password="StrongPassword123!",
            role=User.ROLE_FREELANCER,
            full_name="Bob Developer"
        )
        self.freelancer_profile = FreelancerProfile.objects.create(
            user=self.freelancer_user,
            bio="Senior Full-Stack Django Developer",
            experience_years=5,
            hourly_rate=1000.00,
            availability="available"
        )
        self.freelancer_profile.skills.add(self.skill_python, self.skill_django)

        # Create Backup Freelancer User
        self.backup_user = User.objects.create_user(
            username="backupfreelancer",
            email="backup@example.com",
            password="StrongPassword123!",
            role=User.ROLE_FREELANCER,
            full_name="Charlie Backup"
        )
        self.backup_profile = FreelancerProfile.objects.create(
            user=self.backup_user,
            bio="Expert Python Engineer",
            experience_years=6,
            hourly_rate=1200.00,
            availability="available"
        )
        self.backup_profile.skills.add(self.skill_python, self.skill_django)

        # Create Administrator User
        self.admin_user = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="StrongAdminPassword123!",
            role=User.ROLE_ADMIN,
            full_name="System Administrator"
        )

        # Create a Gig with 3-tier packages
        self.gig = Gig.objects.create(
            freelancer=self.freelancer_user,
            category=self.category,
            title="I will build a custom Django web application",
            description="Professional Django application development with PostgreSQL.",
            tags="python, django, web development",
            status=Gig.STATUS_ACTIVE
        )
        self.pkg_basic = GigPackage.objects.create(
            gig=self.gig,
            tier=GigPackage.BASIC,
            name="Starter Package",
            description="1 page web app",
            price=500.00,
            delivery_days=2,
            revisions=1
        )
        self.pkg_standard = GigPackage.objects.create(
            gig=self.gig,
            tier=GigPackage.STANDARD,
            name="Standard Package",
            description="3 pages web app",
            price=1500.00,
            delivery_days=5,
            revisions=3
        )
        self.pkg_premium = GigPackage.objects.create(
            gig=self.gig,
            tier=GigPackage.PREMIUM,
            name="Premium Package",
            description="Enterprise full stack",
            price=3000.00,
            delivery_days=10,
            revisions=-1
        )

    # -------------------------------------------------------------
    # 1. Authentication & Role Tests
    # -------------------------------------------------------------
    def test_user_registration(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'New Client User',
            'username': 'newclient',
            'email': 'newclient@example.com',
            'role': User.ROLE_CLIENT,
            'password1': 'SafePass12345!',
            'password2': 'SafePass12345!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertFalse(User.objects.filter(username='newclient').exists())
        self.assertTrue(
            EmailVerificationOTP.objects.filter(email='newclient@example.com').exists()
        )

    def test_role_access_security(self):
        # Client trying to access admin dashboard -> forbidden 403
        self.client.login(username="testclient", password="StrongPassword123!")
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

        # Client trying to access freelancer dashboard -> forbidden 403
        response = self.client.get(reverse('freelancer_dashboard'))
        self.assertEqual(response.status_code, 403)

        # Freelancer trying to access admin dashboard -> forbidden 403
        self.client.logout()
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

        # Admin can access admin dashboard
        self.client.logout()
        self.client.login(username="adminuser", password="StrongAdminPassword123!")
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_client_and_freelancer_login_options(self):
        # GET /login/?role=client
        response = self.client.get(reverse('login') + '?role=client')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Login")
        self.assertContains(response, "active-role-client")

        # GET /login/?role=freelancer
        response = self.client.get(reverse('login') + '?role=freelancer')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Freelancer Login")
        self.assertContains(response, "active-role-freelancer")

        # POST Client login
        response = self.client.post(reverse('login'), {
            'username': 'testclient',
            'password': 'StrongPassword123!',
            'selected_role': 'client'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('client_dashboard'))
        self.client.logout()

        # POST Freelancer login
        response = self.client.post(reverse('login'), {
            'username': 'testfreelancer',
            'password': 'StrongPassword123!',
            'selected_role': 'freelancer'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('freelancer_dashboard'))
        self.client.logout()

        # Admin credentials cannot be used through either standard role portal.
        response = self.client.post(reverse('login'), {
            'username': 'adminuser', 'password': 'StrongAdminPassword123!', 'selected_role': 'client'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administrator accounts must use the Administrator Portal')

    def test_dedicated_admin_security_portal(self):
        # Unauthenticated access to admin_dashboard redirects to admin_login
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/admin-login/' in response.url)

        # GET /admin-login/
        response = self.client.get(reverse('admin_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator Sign In")
        self.assertContains(response, "Hirevo Operations Center")

        # Non-admin attempting to login via /admin-login/ is denied
        response = self.client.post(reverse('admin_login'), {
            'username': 'testclient',
            'password': 'StrongPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Access Denied")

        # Administrator logging in via /admin-login/ succeeds and goes to admin_dashboard
        response = self.client.post(reverse('admin_login'), {
            'username': 'adminuser',
            'password': 'StrongAdminPassword123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_dashboard'))
        self.client.logout()

    # -------------------------------------------------------------
    # 2. Marketplace, Search & Filtering Tests
    # -------------------------------------------------------------
    def test_marketplace_search_and_filter(self):
        # Search by keyword
        response = self.client.get(reverse('gig_list') + '?q=Django')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I will build a custom Django web application")

        # Filter by category
        response = self.client.get(reverse('gig_list') + '?category=programming-tech')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I will build a custom Django web application")

        # Non-matching search
        response = self.client.get(reverse('gig_list') + '?q=NonExistentServiceXYZ')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "I will build a custom Django web application")

    # -------------------------------------------------------------
    # 3. Order Lifecycle & Simulated Payment Tests
    # -------------------------------------------------------------
    def test_order_placement_and_deadline_calculation(self):
        self.client.login(username="testclient", password="StrongPassword123!")
        
        # Place Basic Package Order
        response = self.client.post(
            reverse('place_order', kwargs={'gig_id': self.gig.id, 'tier': 'basic'}),
            {'requirements': 'Build authentication and dashboard.'}
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(client=self.client_user, gig=self.gig)
        
        # Check Order ID generation format HV-YYYY-XXXXX
        self.assertTrue(order.order_id.startswith(f"HV-{timezone.now().year}-"))
        self.assertEqual(order.price, 500.00)
        self.assertEqual(order.status, Order.STATUS_PENDING)
        
        # Dynamic deadline should be ~2 days from now
        expected_deadline_min = timezone.now() + timezone.timedelta(days=1, hours=23)
        expected_deadline_max = timezone.now() + timezone.timedelta(days=2, hours=1)
        self.assertTrue(expected_deadline_min <= order.deadline <= expected_deadline_max)

    def test_simulated_payment_execution(self):
        order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
            status=Order.STATUS_PENDING
        )
        self.client.login(username="testclient", password="StrongPassword123!")

        # Process payment simulation
        response = self.client.post(reverse('simulated_payment', kwargs={'order_id': order.id}))
        self.assertEqual(response.status_code, 302)
        
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, Payment.STATUS_PAID)
        self.assertTrue(payment.transaction_id.startswith(f"HV-PAY-{timezone.now().year}-"))
        
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_ACCEPTED)

    # -------------------------------------------------------------
    # 4. Delivery, Revision & Review Lifecycle
    # -------------------------------------------------------------
    def test_delivery_revision_completion_and_review(self):
        order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
            status=Order.STATUS_IN_PROGRESS
        )

        # 1. Freelancer submits delivery
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        response = self.client.post(reverse('freelancer_delivery_submit', kwargs={'order_id': order.id}), {
            'description': 'Initial release delivery for review.'
        })
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_SUBMITTED)
        delivery = Delivery.objects.get(order=order)
        self.assertEqual(delivery.status, Delivery.STATUS_SUBMITTED)

        # 2. Client requests revision
        self.client.logout()
        self.client.login(username="testclient", password="StrongPassword123!")
        response = self.client.post(
            reverse('request_revision', kwargs={'order_id': order.id, 'delivery_id': delivery.id}),
            {'reason': 'Please adjust the header color to emerald green.'}
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_REVISION)
        self.assertEqual(order.revision_count(), 1)

        # 3. Freelancer resubmits
        self.client.logout()
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        self.client.post(reverse('freelancer_delivery_submit', kwargs={'order_id': order.id}), {
            'description': 'Revised release with updated emerald theme.'
        })
        latest_delivery = Delivery.objects.filter(order=order).last()

        # 4. Client approves delivery -> marks completed
        self.client.logout()
        self.client.login(username="testclient", password="StrongPassword123!")
        response = self.client.get(reverse('approve_delivery', kwargs={'order_id': order.id, 'delivery_id': latest_delivery.id}))
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        self.assertIsNotNone(order.completed_at)

        # 5. Client submits rating & review
        response = self.client.post(reverse('create_review', kwargs={'order_id': order.id}), {
            'rating': 5,
            'comment': 'Outstanding work! Very responsive developer.'
        })
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get(order=order)
        self.assertEqual(review.rating, 5)

        # 6. Prevent duplicate reviews on same order
        response = self.client.post(reverse('create_review', kwargs={'order_id': order.id}), {
            'rating': 4,
            'comment': 'Attempting second review.'
        })
        # Should redirect with warning, not create second review
        self.assertEqual(Review.objects.filter(order=order).count(), 1)

    def test_extra_revision_requires_and_records_50_rupee_payment(self):
        order = Order.objects.create(
            client=self.client_user, freelancer=self.freelancer_user, gig=self.gig,
            package=self.pkg_basic, price=self.pkg_basic.price, status=Order.STATUS_SUBMITTED
        )
        delivery = Delivery.objects.create(order=order, freelancer=self.freelancer_user, description='Initial delivery')
        Revision.objects.create(order=order, client=self.client_user, reason='Included revision already used')

        self.client.login(username='testclient', password='StrongPassword123!')
        response = self.client.post(
            reverse('request_revision', kwargs={'order_id': order.id, 'delivery_id': delivery.id}),
            {'reason': 'One more adjustment'}
        )
        charge = RevisionCharge.objects.get(revision__order=order)
        self.assertRedirects(response, reverse('pay_revision_charge', kwargs={'charge_id': charge.id}))
        self.assertEqual(charge.amount, 50)
        self.assertEqual(charge.status, RevisionCharge.STATUS_PENDING)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_SUBMITTED)

        response = self.client.post(reverse('pay_revision_charge', kwargs={'charge_id': charge.id}))
        self.assertRedirects(response, reverse('client_order_detail', kwargs={'order_id': order.id}))
        charge.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(charge.status, RevisionCharge.STATUS_PAID)
        self.assertEqual(order.status, Order.STATUS_REVISION)
        earnings = calculate_freelancer_earnings(self.freelancer_user)
        self.assertEqual(earnings['extra_revisions'], 50)
        self.assertEqual(earnings['net_earnings'], 50)

    def test_freelancer_must_be_verified_before_creating_a_gig(self):
        self.client.login(username='testfreelancer', password='StrongPassword123!')
        response = self.client.get(reverse('freelancer_gig_create'))
        self.assertRedirects(response, reverse('freelancer_verification'))

        FreelancerVerification.objects.create(
            user=self.freelancer_user,
            document_type=FreelancerVerification.DOCUMENT_AADHAAR,
            document_file='verification_documents/id.pdf',
            selfie_image='verification_selfies/selfie.jpg',
            status=FreelancerVerification.STATUS_APPROVED,
            liveness_status=FreelancerVerification.STATUS_APPROVED,
        )
        response = self.client.get(reverse('freelancer_gig_create'))
        self.assertEqual(response.status_code, 200)

    def test_client_and_freelancer_can_send_direct_messages(self):
        """Both account types can begin a thread from their project contact."""
        order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
        )

        self.client.login(username="testclient", password="StrongPassword123!")
        response = self.client.post(
            reverse('messages_thread', kwargs={'user_id': self.freelancer_user.id}),
            {'content': 'Could you confirm the project timeline?'}
        )
        self.assertRedirects(
            response,
            reverse('messages_thread', kwargs={'user_id': self.freelancer_user.id})
        )
        client_message = Message.objects.get(sender=self.client_user)
        self.assertEqual(client_message.receiver, self.freelancer_user)
        self.assertEqual(client_message.order, order)

        self.client.logout()
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        response = self.client.post(
            reverse('messages_thread', kwargs={'user_id': self.client_user.id}),
            {'content': 'Yes, I will share an update today.'}
        )
        self.assertRedirects(
            response,
            reverse('messages_thread', kwargs={'user_id': self.client_user.id})
        )
        freelancer_message = Message.objects.get(sender=self.freelancer_user)
        self.assertEqual(freelancer_message.receiver, self.client_user)
        self.assertEqual(freelancer_message.order, order)

    def test_order_creates_visible_project_chat_contact_before_first_message(self):
        Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
        )

        self.client.login(username="testclient", password="StrongPassword123!")
        client_inbox = self.client.get(reverse('messages_inbox'))
        self.assertContains(client_inbox, self.freelancer_user.username)
        self.assertContains(client_inbox, 'Start a conversation for your project...')

        self.client.logout()
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        freelancer_inbox = self.client.get(reverse('messages_inbox'))
        self.assertContains(freelancer_inbox, self.client_user.username)

    # -------------------------------------------------------------
    # 5. AI Recommendation Engine Tests
    # -------------------------------------------------------------
    def test_ai_recommendation_scoring(self):
        # Deterministic scoring tests
        skills = [self.skill_python, self.skill_django]
        
        # Exact skill match
        skill_score = _skill_match_score(skills, ["Python", "Django"])
        self.assertEqual(skill_score, 100.0)

        # Partial skill match (1 of 2)
        partial_score = _skill_match_score(skills, ["Python", "React"])
        self.assertEqual(partial_score, 50.0)

        # Experience normalization (5 yrs -> 70%)
        exp_score = _experience_score(5)
        self.assertEqual(exp_score, 70.0)

        # Full recommendation evaluation
        results = recommend_freelancers(
            project_title="Build Django REST API",
            project_description="Need an experienced Django engineer",
            required_skills=["Python", "Django"],
            budget=1500.00
        )
        self.assertTrue(len(results) > 0)
        top_match = results[0]
        self.assertIn('final_score', top_match)
        self.assertIn('skill_score', top_match)
        self.assertIn('nlp_score', top_match)
        self.assertIn('experience_score', top_match)
        self.assertIn('rating_score', top_match)
        self.assertTrue(top_match['final_score'] > 50.0)

    # -------------------------------------------------------------
    # 6. Automatic Delay Detection & 5% Penalty Tests
    # -------------------------------------------------------------
    def test_automatic_delay_detection_and_penalty(self):
        # Create an overdue active order (deadline 2 days in the past)
        past_deadline = timezone.now() - timezone.timedelta(days=2)
        overdue_order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_standard,
            price=20000.00,
            status=Order.STATUS_IN_PROGRESS,
            deadline=past_deadline
        )

        # Also create a completed order with past deadline (should NOT receive penalty)
        completed_order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_standard,
            price=15000.00,
            status=Order.STATUS_COMPLETED,
            deadline=past_deadline
        )

        # Run delay detection service
        delayed_count = check_and_apply_delays()
        self.assertEqual(delayed_count, 1)

        overdue_order.refresh_from_db()
        self.assertEqual(overdue_order.status, Order.STATUS_DELAYED)

        # Penalty must be 5% of order price: 5% of 20000 = 1000
        penalty = Penalty.objects.get(order=overdue_order)
        self.assertEqual(penalty.freelancer, self.freelancer_user)
        self.assertEqual(penalty.order_amount, 20000.00)
        self.assertEqual(penalty.percentage, 5.00)
        self.assertEqual(penalty.penalty_amount, 1000.00)
        self.assertEqual(penalty.status, Penalty.STATUS_APPLIED)

        # Completed order must NOT receive a penalty
        self.assertFalse(Penalty.objects.filter(order=completed_order).exists())

        # Running delay check again must NOT create duplicate penalties
        second_run = check_and_apply_delays()
        self.assertEqual(Penalty.objects.filter(order=overdue_order).count(), 1)

    # -------------------------------------------------------------
    # 7. Administrator-Controlled Backup Freelancer Assignment Tests
    # -------------------------------------------------------------
    def test_admin_only_backup_assignment_security(self):
        past_deadline = timezone.now() - timezone.timedelta(days=1)
        delayed_order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_standard,
            price=2000.00,
            status=Order.STATUS_DELAYED,
            deadline=past_deadline
        )

        # Client cannot assign backup -> 403 Forbidden
        self.client.login(username="testclient", password="StrongPassword123!")
        response = self.client.post(
            reverse('admin_assign_backup', kwargs={'order_id': delayed_order.id}),
            {'backup_freelancer': self.backup_user.id, 'reason': 'Client attempt'}
        )
        self.assertEqual(response.status_code, 403)

        # Freelancer cannot assign backup -> 403 Forbidden
        self.client.logout()
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        response = self.client.post(
            reverse('admin_assign_backup', kwargs={'order_id': delayed_order.id}),
            {'backup_freelancer': self.backup_user.id, 'reason': 'Freelancer attempt'}
        )
        self.assertEqual(response.status_code, 403)

        # Only Admin can assign backup
        self.client.logout()
        self.client.login(username="adminuser", password="StrongAdminPassword123!")
        response = self.client.post(
            reverse('admin_assign_backup', kwargs={'order_id': delayed_order.id}),
            {'backup_freelancer': self.backup_user.id, 'reason': 'Primary delayed; assigned backup.'}
        )
        self.assertEqual(response.status_code, 302)

        assignment = BackupAssignment.objects.get(order=delayed_order)
        self.assertEqual(assignment.primary_freelancer, self.freelancer_user)
        self.assertEqual(assignment.backup_freelancer, self.backup_user)
        self.assertEqual(assignment.assigned_by, self.admin_user)
        self.assertEqual(assignment.status, BackupAssignment.STATUS_ASSIGNED)

        # Backup freelancer accepts assignment
        self.client.logout()
        self.client.login(username="backupfreelancer", password="StrongPassword123!")
        response = self.client.get(
            reverse('freelancer_backup_respond', kwargs={'assignment_id': assignment.id, 'action': 'accept'})
        )
        self.assertEqual(response.status_code, 302)
        
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, BackupAssignment.STATUS_ACCEPTED)
        
        delayed_order.refresh_from_db()
        self.assertEqual(delayed_order.status, Order.STATUS_BACKUP)
        self.assertEqual(delayed_order.freelancer, self.backup_user)

    # -------------------------------------------------------------
    # 8. REST API Endpoints Tests
    # -------------------------------------------------------------
    def test_rest_api_endpoints(self):
        # Public Gigs API
        response = self.client.get(reverse('api_gigs'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data['results']) >= 1)

        # Public Categories API
        response = self.client.get(reverse('api_categories'))
        self.assertEqual(response.status_code, 200)

        # Public AI Recommendations API
        response = self.client.get(reverse('api_recommendations') + '?skills=Python,Django')
        self.assertEqual(response.status_code, 200)
        self.assertIn('recommended_freelancers', response.data)
        self.assertIn('recommended_gigs', response.data)

    # -------------------------------------------------------------
    # 9. Email Notifications & Registration OTP Verification Tests
    # -------------------------------------------------------------
    def test_registration_with_otp_verification(self):
        """Verify registration sends OTP email, validates code, and activates account."""
        mail.outbox.clear()
        
        # Step 1: Submit Registration Form
        response = self.client.post(reverse('register'), {
            'full_name': 'New Verified Client',
            'username': 'newclientotp',
            'email': 'newclient@example.com',
            'role': User.ROLE_CLIENT,
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_otp'))

        # User is not created in DB yet
        self.assertFalse(User.objects.filter(username='newclientotp').exists())

        # Email was sent with 6-digit OTP code
        self.assertEqual(len(mail.outbox), 1)
        otp_email = mail.outbox[0]
        self.assertIn('newclient@example.com', otp_email.to)
        self.assertIn('Your Account Verification Code', otp_email.subject)

        otp_record = EmailVerificationOTP.objects.get(email='newclient@example.com')
        self.assertEqual(len(otp_record.otp_code), 6)

        # Step 2: Try invalid OTP code
        invalid_response = self.client.post(reverse('verify_otp'), {'otp_code': '000000'})
        self.assertEqual(invalid_response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newclientotp').exists())

        # Step 3: Enter valid OTP code
        valid_response = self.client.post(reverse('verify_otp'), {'otp_code': otp_record.otp_code})
        self.assertEqual(valid_response.status_code, 302)
        self.assertRedirects(valid_response, reverse('client_dashboard'))

        # User is now created and email verified
        created_user = User.objects.get(username='newclientotp')
        self.assertTrue(created_user.is_email_verified)
        self.assertTrue(created_user.is_client())
        self.assertTrue(hasattr(created_user, 'client_profile'))

    def test_order_assigned_email_notification(self):
        """Freelancer and Client receive email when order is placed."""
        mail.outbox.clear()
        self.client.login(username="testclient", password="StrongPassword123!")

        response = self.client.post(
            reverse('place_order', kwargs={'gig_id': self.gig.id, 'tier': 'basic'}),
            {'requirements': 'Build an automated email notification system'}
        )
        self.assertEqual(response.status_code, 302)

        # Expect emails sent to freelancer and client
        recipients = [m.to[0] for m in mail.outbox]
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(self.freelancer_user.email, recipients)
        self.assertIn(self.client_user.email, recipients)

    def test_freelancer_status_update_email_notifications(self):
        """Client receives emails when freelancer updates status (accepts order, submits delivery)."""
        order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
            requirements="Test requirements",
            status=Order.STATUS_PENDING
        )

        # 1. Freelancer accepts order
        mail.outbox.clear()
        self.client.login(username="testfreelancer", password="StrongPassword123!")
        response = self.client.get(
            reverse('freelancer_order_respond', kwargs={'order_id': order.id, 'action': 'accept'})
        )
        self.assertEqual(response.status_code, 302)

        # Client receives "In Progress" update email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.client_user.email, mail.outbox[-1].to)
        self.assertIn("Project Accepted", mail.outbox[-1].subject)

        # 2. Freelancer submits delivery
        mail.outbox.clear()
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile("delivery.zip", b"dummy delivery contents")
        response = self.client.post(
            reverse('freelancer_delivery_submit', kwargs={'order_id': order.id}),
            {'description': 'Final delivery version 1.0', 'delivery_file': test_file}
        )
        self.assertEqual(response.status_code, 302)

        # Client receives "Deliverables Submitted" email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.client_user.email, mail.outbox[-1].to)
        self.assertIn("Deliverables Submitted", mail.outbox[-1].subject)

    def test_delay_detection_email_notifications(self):
        """Client and Freelancer receive emails when delay detection triggers on overdue project."""
        past_deadline = timezone.now() - timezone.timedelta(days=2)
        delayed_order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
            requirements="Delayed project scope",
            status=Order.STATUS_IN_PROGRESS,
            deadline=past_deadline
        )

        mail.outbox.clear()
        count = check_and_apply_delays()
        self.assertEqual(count, 1)

        delayed_order.refresh_from_db()
        self.assertEqual(delayed_order.status, Order.STATUS_DELAYED)

        # Emails sent to both Client and Primary Freelancer
        recipients = [m.to[0] for m in mail.outbox]
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(self.client_user.email, recipients)
        self.assertIn(self.freelancer_user.email, recipients)

    def test_backup_freelancer_email_notifications(self):
        """Backup freelancer and client receive emails when backup is assigned."""
        past_deadline = timezone.now() - timezone.timedelta(days=2)
        delayed_order = Order.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            gig=self.gig,
            package=self.pkg_basic,
            price=self.pkg_basic.price,
            requirements="Delayed project scope",
            status=Order.STATUS_DELAYED,
            deadline=past_deadline
        )

        mail.outbox.clear()
        assignment = assign_backup_freelancer(
            order=delayed_order,
            backup_freelancer=self.backup_user,
            admin_user=self.admin_user,
            reason="Primary freelancer unresponsive past deadline"
        )

        # Emails sent to Backup Freelancer and Client
        recipients = [m.to[0] for m in mail.outbox]
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(self.backup_user.email, recipients)
        self.assertIn(self.client_user.email, recipients)
