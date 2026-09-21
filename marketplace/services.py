from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .models import Order, Penalty, Notification, ProjectHistory, BackupAssignment, Payment, RevisionCharge


def create_notification(user, title, message, link=''):
    """Create a persistent notification for a user."""
    if user:
        return Notification.objects.create(user=user, title=title, message=message, link=link)
    return None


def add_project_history(order, action, description, performed_by=None):
    """Record an audit trail event in the ProjectHistory."""
    if order:
        return ProjectHistory.objects.create(
            order=order, action=action, description=description, performed_by=performed_by
        )
    return None


def check_and_apply_delays():
    """
    Automatic delay detection service.
    Scans active non-completed orders past their deadline:
    1. Sets order status to DELAYED.
    2. Calculates and records a 5% penalty for the primary freelancer.
    3. Records ProjectHistory entries.
    4. Issues notifications & emails to Administrator, Freelancer, and Client.
    Guarantees no duplicate penalties are created.
    """
    now = timezone.now()
    active_statuses = [
        Order.STATUS_PENDING,
        Order.STATUS_ACCEPTED,
        Order.STATUS_IN_PROGRESS,
        Order.STATUS_SUBMITTED,
        Order.STATUS_REVISION,
    ]
    overdue_orders = Order.objects.filter(
        deadline__lt=now,
        status__in=active_statuses
    ).select_related('freelancer', 'client', 'gig')

    count = 0
    User = get_user_model()

    for order in overdue_orders:
        with transaction.atomic():
            order.status = Order.STATUS_DELAYED
            order.save(update_fields=['status', 'updated_at'])

            # Ensure penalty is created only once
            if not Penalty.objects.filter(order=order).exists():
                penalty = Penalty.objects.create(
                    order=order,
                    freelancer=order.freelancer,
                    order_amount=order.price,
                    percentage=5.00,
                    status=Penalty.STATUS_APPLIED,
                    reason=f"Missed deadline of {order.deadline.strftime('%d %b %Y, %I:%M %p')}"
                )

                add_project_history(
                    order=order,
                    action="Delay Detected",
                    description=f"Project deadline ({order.deadline.strftime('%d %b %Y')}) passed without completion. Status set to Delayed.",
                    performed_by=None
                )
                add_project_history(
                    order=order,
                    action="Penalty Applied",
                    description=f"Automatic penalty of ₹{penalty.penalty_amount} (5% of ₹{order.price}) applied to {order.freelancer.username}.",
                    performed_by=None
                )

                # Notify Admins
                admins = User.objects.filter(is_staff=True) | User.objects.filter(role=User.ROLE_ADMIN)
                for admin in admins.distinct():
                    msg = f"Order {order.order_id} ({order.gig.title}) is delayed. Primary freelancer: {order.freelancer.username}. Backup assignment required."
                    create_notification(
                        user=admin,
                        title="Delayed Project Alert",
                        message=msg,
                        link=f"/admin-dashboard/orders/{order.id}/assign-backup/"
                    )
                    
                    # Send email alert to admin
                    if admin.email:
                        try:
                            send_mail(
                                'Action Required: Delayed Project Alert',
                                f"Hello {admin.username},\n\n{msg}\n\nPlease log in to assign a backup freelancer.",
                                settings.DEFAULT_FROM_EMAIL,
                                [admin.email],
                                fail_silently=True,
                            )
                        except Exception:
                            pass

                # Notify Primary Freelancer
                create_notification(
                    user=order.freelancer,
                    title="Order Marked Delayed - Penalty Applied",
                    message=f"Order {order.order_id} missed its deadline. A 5% penalty (₹{penalty.penalty_amount}) has been recorded.",
                    link=f"/freelancer/orders/{order.id}/"
                )

                # Notify Client
                create_notification(
                    user=order.client,
                    title="Project Delayed Update",
                    message=f"Your order {order.order_id} is currently overdue. Hirevo platform management has been alerted for continuity assistance.",
                    link=f"/client/orders/{order.id}/"
                )

            count += 1

    return count


def assign_backup_freelancer(order, backup_freelancer, admin_user, reason):
    """
    Administrator assigns a qualified backup freelancer to a delayed project.
    """
    with transaction.atomic():
        assignment = BackupAssignment.objects.create(
            order=order,
            primary_freelancer=order.freelancer,
            backup_freelancer=backup_freelancer,
            assigned_by=admin_user,
            reason=reason,
            status=BackupAssignment.STATUS_ASSIGNED
        )

        add_project_history(
            order=order,
            action="Backup Assigned",
            description=f"Admin {admin_user.username} assigned backup freelancer {backup_freelancer.username}. Reason: {reason}",
            performed_by=admin_user
        )

        # Notify Backup Freelancer
        create_notification(
            user=backup_freelancer,
            title="Backup Project Assigned",
            message=f"You have been assigned as a backup freelancer for Order {order.order_id} by Administrator {admin_user.username}.",
            link=f"/freelancer/backup-assignments/"
        )

        # Notify Client
        create_notification(
            user=order.client,
            title="Backup Freelancer Assigned",
            message=f"Administrator has assigned backup freelancer {backup_freelancer.username} to your order {order.order_id} to maintain delivery schedule.",
            link=f"/client/orders/{order.id}/"
        )

        return assignment



def calculate_freelancer_earnings(freelancer):
    """
    Calculate dynamic financial summary for a freelancer.
    """
    paid_payments = Payment.objects.filter(freelancer=freelancer, status=Payment.STATUS_PAID)
    completed_earnings = sum(p.amount for p in paid_payments)
    extra_revision_earnings = sum(
        charge.amount for charge in RevisionCharge.objects.filter(
            revision__order__freelancer=freelancer,
            status=RevisionCharge.STATUS_PAID,
        )
    )
    gross_earnings = completed_earnings + extra_revision_earnings

    pending_orders = Order.objects.filter(
        freelancer=freelancer,
        status__in=[Order.STATUS_ACCEPTED, Order.STATUS_IN_PROGRESS, Order.STATUS_SUBMITTED, Order.STATUS_REVISION]
    )
    pending_earnings = sum(o.price for o in pending_orders)

    penalties = Penalty.objects.filter(freelancer=freelancer, status=Penalty.STATUS_APPLIED)
    total_penalties = sum(p.penalty_amount for p in penalties)

    net_earnings = max(0, gross_earnings - total_penalties)

    return {
        'total': gross_earnings,
        'completed': completed_earnings,
        'extra_revisions': extra_revision_earnings,
        'extra_revision_count': RevisionCharge.objects.filter(
            revision__order__freelancer=freelancer,
            status=RevisionCharge.STATUS_PAID,
        ).count(),
        'pending': pending_earnings,
        'penalties': total_penalties,
        'net_earnings': net_earnings,
        'completed_count': paid_payments.count(),
    }


class GovernmentIDVerificationService:
    """
    Mock service to simulate checking an Aadhaar number against a government database API via OTP.
    """
    
    @staticmethod
    def verify_aadhaar(aadhaar_number, otp_code, user):
        """
        Simulate an Aadhaar API validation call.
        Returns a dictionary with 'is_valid' boolean and a 'message'.
        """
        import time
        
        # Simulate network latency
        time.sleep(1.0)
        
        if otp_code == '123456':
            return {
                'is_valid': True,
                'status': 'approved',
                'message': f'Successfully verified Aadhaar number {aadhaar_number} with government records.'
            }
        else:
            return {
                'is_valid': False,
                'status': 'pending',
                'message': f'Invalid OTP or automated check failed. Flagged for manual review.'
            }

class CashfreeAadhaarService:
    """
    Service for interacting with Cashfree Verification Suite for Aadhaar KYC.
    Uses placeholders from settings if credentials are not configured.
    """
    
    @staticmethod
    def _get_headers():
        from django.conf import settings
        return {
            'x-client-id': settings.CASHFREE_CLIENT_ID,
            'x-client-secret': settings.CASHFREE_CLIENT_SECRET,
            'Content-Type': 'application/json'
        }
        
    @staticmethod
    def _get_base_url():
        from django.conf import settings
        if getattr(settings, 'CASHFREE_ENV', 'TEST') == 'PROD':
            return 'https://api.cashfree.com/verification'
        return 'https://sandbox.cashfree.com/verification'

    @staticmethod
    def send_otp(aadhaar_number):
        import requests
        from django.conf import settings
        
        # If placeholders are used, simulate the response so the UI still works
        if settings.CASHFREE_CLIENT_ID == 'placeholder_client_id':
            import time
            time.sleep(1)
            return {'success': True, 'ref_id': 'mock_ref_12345'}

        url = f"{CashfreeAadhaarService._get_base_url()}/offline-aadhaar/otp"
        payload = {"aadhaar_number": aadhaar_number}
        try:
            response = requests.post(url, json=payload, headers=CashfreeAadhaarService._get_headers())
            data = response.json()
            if response.status_code == 200 and data.get('status') == 'SUCCESS':
                return {'success': True, 'ref_id': data.get('ref_id')}
            return {'success': False, 'message': data.get('message', 'Failed to send OTP')}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @staticmethod
    def verify_otp(ref_id, otp):
        import requests
        from django.conf import settings
        
        # If placeholders are used, simulate the verification
        if settings.CASHFREE_CLIENT_ID == 'placeholder_client_id':
            import time
            time.sleep(1)
            if otp == '123456':
                return {'success': True, 'message': 'Mock OTP Verified'}
            return {'success': False, 'message': 'Invalid Mock OTP'}

        url = f"{CashfreeAadhaarService._get_base_url()}/offline-aadhaar/verify"
        payload = {"ref_id": ref_id, "otp": otp}
        try:
            response = requests.post(url, json=payload, headers=CashfreeAadhaarService._get_headers())
            data = response.json()
            if response.status_code == 200 and data.get('status') == 'VALID':
                return {'success': True, 'message': 'Aadhaar Verified', 'data': data}
            return {'success': False, 'message': data.get('message', 'Invalid OTP')}
        except Exception as e:
            return {'success': False, 'message': str(e)}
