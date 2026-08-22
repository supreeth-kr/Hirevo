import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_hirevo_email(subject, template_name, context, recipient_list, from_email=None, fail_silently=True):
    """
    Central email dispatcher for Hirevo.
    Renders both rich HTML and clean plain-text fallback.
    Never crashes transaction on mail delivery issues when fail_silently=True.
    """
    if not recipient_list:
        return False

    # Filter out empty or invalid strings
    valid_recipients = [r.strip() for r in recipient_list if r and isinstance(r, str) and '@' in r]
    if not valid_recipients:
        logger.warning(f"send_hirevo_email: No valid recipient found in {recipient_list}")
        return False

    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'Hirevo <notifications@hirevo.com>')

    full_context = {
        'site_url': site_url,
        'site_name': 'Hirevo',
        'current_year': timezone.now().year,
        'subject': subject,
        **context
    }

    try:
        html_content = render_to_string(template_name, full_context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject=f"[Hirevo] {subject}",
            body=text_content,
            from_email=sender,
            to=valid_recipients
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=fail_silently)
        logger.info(f"Email sent successfully to {valid_recipients}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error sending email to {valid_recipients} ({subject}): {e}", exc_info=True)
        if not fail_silently:
            raise
        return False


def send_registration_otp_email(email, full_name, otp_code, expiry_minutes=10):
    """Send 6-digit registration OTP verification code."""
    context = {
        'full_name': full_name or 'User',
        'email': email,
        'otp_code': otp_code,
        'expiry_minutes': expiry_minutes,
    }
    return send_hirevo_email(
        subject="Your Account Verification Code",
        template_name="emails/registration_otp.html",
        context=context,
        recipient_list=[email]
    )


def send_order_assigned_email(order):
    """
    Dispatched when a project/order is placed:
    1. Freelancer receives project assignment notification.
    2. Client receives order placement confirmation.
    """
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

    # 1. To Freelancer
    freelancer_email = order.freelancer.email
    if freelancer_email:
        send_hirevo_email(
            subject=f"New Project Assigned: {order.order_id} - {order.gig.title}",
            template_name="emails/order_assigned_freelancer.html",
            context={
                'order': order,
                'user': order.freelancer,
                'counterpart': order.client,
                'project_url': f"{site_url}/freelancer/orders/{order.id}/",
                'is_freelancer': True,
            },
            recipient_list=[freelancer_email]
        )

    # 2. To Client
    client_email = order.client.email
    if client_email:
        send_hirevo_email(
            subject=f"Order Placed Successfully: {order.order_id} - {order.gig.title}",
            template_name="emails/order_placed_client.html",
            context={
                'order': order,
                'user': order.client,
                'counterpart': order.freelancer,
                'project_url': f"{site_url}/client/orders/{order.id}/",
                'is_client': True,
            },
            recipient_list=[client_email]
        )


def send_order_status_update_email(order, new_status, extra_context=None):
    """
    Dispatched when freelancer or client changes project status:
    - in_progress (Freelancer accepted) -> Client notified
    - rejected (Freelancer declined) -> Client notified
    - submitted (Freelancer submitted deliverables) -> Client notified
    - revision_requested (Client requested revision) -> Freelancer notified
    - completed (Client approved deliverable) -> Freelancer notified
    """
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    extra = extra_context or {}

    if new_status == 'in_progress':
        # Freelancer accepted -> notify client
        if order.client.email:
            send_hirevo_email(
                subject=f"Project Accepted: {order.order_id} is now In Progress",
                template_name="emails/order_status_client.html",
                context={
                    'order': order,
                    'user': order.client,
                    'freelancer': order.freelancer,
                    'status_title': "Project Accepted & In Progress",
                    'status_badge': "In Progress",
                    'status_color': "#3b82f6",
                    'message_text': f"Great news! Freelancer {order.freelancer.full_name or order.freelancer.username} has accepted your order and started working on the deliverables.",
                    'project_url': f"{site_url}/client/orders/{order.id}/",
                    'action_label': "View Project Workspace",
                    **extra
                },
                recipient_list=[order.client.email]
            )

    elif new_status == 'rejected':
        # Freelancer declined -> notify client
        if order.client.email:
            send_hirevo_email(
                subject=f"Order Update: {order.order_id} was Declined",
                template_name="emails/order_status_client.html",
                context={
                    'order': order,
                    'user': order.client,
                    'freelancer': order.freelancer,
                    'status_title': "Order Declined by Freelancer",
                    'status_badge': "Declined",
                    'status_color': "#ef4444",
                    'message_text': f"Freelancer {order.freelancer.full_name or order.freelancer.username} was unable to accept your order {order.order_id}. You can explore similar talent and gigs on the marketplace.",
                    'project_url': f"{site_url}/gigs/",
                    'action_label': "Browse Other Freelancers",
                    **extra
                },
                recipient_list=[order.client.email]
            )

    elif new_status == 'submitted':
        # Freelancer submitted delivery -> notify client
        if order.client.email:
            send_hirevo_email(
                subject=f"Action Required: Deliverables Submitted for Order {order.order_id}",
                template_name="emails/order_status_client.html",
                context={
                    'order': order,
                    'user': order.client,
                    'freelancer': order.freelancer,
                    'status_title': "Work Deliverables Submitted",
                    'status_badge': "In Review",
                    'status_color': "#8b5cf6",
                    'message_text': f"Freelancer {order.freelancer.full_name or order.freelancer.username} has submitted the work for order {order.order_id}. Please review the submitted files and either approve the project or request a revision.",
                    'project_url': f"{site_url}/client/orders/{order.id}/",
                    'action_label': "Review Deliverables",
                    **extra
                },
                recipient_list=[order.client.email]
            )

    elif new_status == 'revision_requested':
        # Client requested revision -> notify freelancer
        target_freelancer = order.freelancer
        if target_freelancer and target_freelancer.email:
            send_hirevo_email(
                subject=f"Revision Requested: Order {order.order_id}",
                template_name="emails/order_status_freelancer.html",
                context={
                    'order': order,
                    'user': target_freelancer,
                    'client': order.client,
                    'status_title': "Revision Requested",
                    'status_badge': "Revision",
                    'status_color': "#f59e0b",
                    'message_text': f"Client {order.client.full_name or order.client.username} has requested changes on order {order.order_id}. Please review the feedback and submit updated deliverables.",
                    'project_url': f"{site_url}/freelancer/orders/{order.id}/",
                    'action_label': "View Revision Notes",
                    **extra
                },
                recipient_list=[target_freelancer.email]
            )

    elif new_status == 'completed':
        # Client approved -> notify freelancer
        target_freelancer = order.freelancer
        if target_freelancer and target_freelancer.email:
            send_hirevo_email(
                subject=f"Congratulations! Order {order.order_id} Approved & Completed",
                template_name="emails/order_status_freelancer.html",
                context={
                    'order': order,
                    'user': target_freelancer,
                    'client': order.client,
                    'status_title': "Project Approved & Completed",
                    'status_badge': "Completed",
                    'status_color': "#10b981",
                    'message_text': f"Client {order.client.full_name or order.client.username} has approved your delivery for order {order.order_id}. Funds have been released to your earnings ledger.",
                    'project_url': f"{site_url}/freelancer/orders/{order.id}/",
                    'action_label': "View Completed Order",
                    **extra
                },
                recipient_list=[target_freelancer.email]
            )


def send_order_delayed_email(order, penalty=None):
    """
    Dispatched when automatic delay watcher identifies an overdue project:
    1. Client receives delay notice explaining platform backup continuity.
    2. Primary freelancer receives overdue warning & 5% penalty notice.
    """
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

    # 1. To Client
    if order.client.email:
        send_hirevo_email(
            subject=f"Urgent Notice: Delivery Delay on Order {order.order_id}",
            template_name="emails/order_delayed_client.html",
            context={
                'order': order,
                'user': order.client,
                'freelancer': order.freelancer,
                'project_url': f"{site_url}/client/orders/{order.id}/",
            },
            recipient_list=[order.client.email]
        )

    # 2. To Primary Freelancer
    if order.freelancer.email:
        send_hirevo_email(
            subject=f"Important Notice: Order {order.order_id} Marked Delayed",
            template_name="emails/order_delayed_freelancer.html",
            context={
                'order': order,
                'penalty': penalty,
                'user': order.freelancer,
                'project_url': f"{site_url}/freelancer/orders/{order.id}/",
            },
            recipient_list=[order.freelancer.email]
        )


def send_backup_assigned_email(order, backup_freelancer, admin_user, reason):
    """
    Dispatched when Administrator assigns a backup freelancer to an overdue project:
    1. Backup Freelancer receives invitation with scope & project history.
    2. Client receives notification that backup freelancer has been assigned.
    """
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

    # 1. To Backup Freelancer
    if backup_freelancer.email:
        send_hirevo_email(
            subject=f"Backup Project Assignment: Order {order.order_id}",
            template_name="emails/backup_assigned_freelancer.html",
            context={
                'order': order,
                'backup_freelancer': backup_freelancer,
                'admin_user': admin_user,
                'reason': reason,
                'project_url': f"{site_url}/freelancer/backup-assignments/",
            },
            recipient_list=[backup_freelancer.email]
        )

    # 2. To Client
    if order.client.email:
        send_hirevo_email(
            subject=f"Project Continuity Update: Backup Freelancer Assigned for {order.order_id}",
            template_name="emails/order_status_client.html",
            context={
                'order': order,
                'user': order.client,
                'freelancer': backup_freelancer,
                'status_title': "Backup Freelancer Assigned",
                'status_badge': "Backup Assigned",
                'status_color': "#06b6d4",
                'message_text': f"To ensure your project delivery without further delay, platform management has assigned backup specialist {backup_freelancer.full_name or backup_freelancer.username} to your order {order.order_id}.",
                'project_url': f"{site_url}/client/orders/{order.id}/",
                'action_label': "View Project Details",
            },
            recipient_list=[order.client.email]
        )


def send_backup_accepted_email(order, backup_freelancer):
    """Dispatched when backup freelancer accepts the assignment."""
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    if order.client.email:
        send_hirevo_email(
            subject=f"Project Resumed: Backup Freelancer Accepted Order {order.order_id}",
            template_name="emails/order_status_client.html",
            context={
                'order': order,
                'user': order.client,
                'freelancer': backup_freelancer,
                'status_title': "Backup Freelancer Resumed Work",
                'status_badge': "In Progress (Backup)",
                'status_color': "#0284c7",
                'message_text': f"Backup specialist {backup_freelancer.full_name or backup_freelancer.username} has accepted the assignment for order {order.order_id} and resumed work on your project.",
                'project_url': f"{site_url}/client/orders/{order.id}/",
                'action_label': "View Project Workspace",
            },
            recipient_list=[order.client.email]
        )


def send_password_reset_otp_email(email, full_name, otp_code, expiry_minutes=10):
    """Send 6-digit password reset OTP verification code."""
    context = {
        'full_name': full_name or 'User',
        'email': email,
        'otp_code': otp_code,
        'expiry_minutes': expiry_minutes,
    }
    print(f"✅ PASSWORD RESET OTP Email prepared for {email} - OTP: {otp_code}")
    return send_hirevo_email(
        subject="Your Password Reset Code",
        template_name="emails/password_reset_otp.html",
        context=context,
        recipient_list=[email],
        fail_silently=False
    )
