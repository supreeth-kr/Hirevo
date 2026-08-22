"""Email utilities for OTP verification and notifications"""
import random
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailOTP


def generate_otp(length=6):
    """Generate a random OTP"""
    return ''.join(random.choices(string.digits, k=length))


def send_otp_email(email, otp=None):
    """Generate and send OTP to email"""
    if not otp:
        otp = generate_otp()
    
    # Delete existing OTP for this email
    EmailOTP.objects.filter(email=email, is_used=False).delete()
    
    # Create new OTP record
    otp_record = EmailOTP.objects.create(
        email=email,
        otp=otp,
        expires_at=timezone.now() + timedelta(minutes=10)
    )
    
    subject = "Email Verification - Hirevo Marketplace"
    message = f"""
Hello,

Your OTP for email verification is: {otp}

This OTP will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
Hirevo Team
"""
    
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="background-color: white; padding: 30px; border-radius: 5px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Email Verification</h2>
                <p>Hello,</p>
                <p>Your OTP for email verification is:</p>
                <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                    <h1 style="color: #007bff; letter-spacing: 5px; margin: 0;">{otp}</h1>
                </div>
                <p style="color: #666;">This OTP will expire in <strong>10 minutes</strong>.</p>
                <p style="color: #999; font-size: 12px;">If you didn't request this, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">Best regards,<br><strong>Hirevo Team</strong></p>
            </div>
        </body>
    </html>
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [email],
            html_message=html_message,
            fail_silently=False
        )
        print(f"✅ OTP Email sent successfully to {email} - OTP: {otp}")
    except Exception as e:
        print(f"❌ ERROR sending OTP email to {email}: {str(e)}")
        print(f"Email Backend: {settings.EMAIL_BACKEND}")
        print(f"Email Host: {settings.EMAIL_HOST}")
        print(f"Email User: {settings.EMAIL_HOST_USER}")
        raise
    
    return otp_record


def verify_otp(email, otp):
    """Verify if the provided OTP is correct and not expired"""
    try:
        otp_record = EmailOTP.objects.get(
            email=email,
            otp=otp,
            is_used=False,
            expires_at__gt=timezone.now()
        )
        otp_record.is_used = True
        otp_record.verified_at = timezone.now()
        otp_record.save()
        return True, otp_record
    except EmailOTP.DoesNotExist:
        return False, None


def send_order_status_email(order, status, recipient_email, recipient_name, is_freelancer=False):
    """Send email notification when order status changes"""
    
    subject = f"Order Status Update - {order.gig.title}"
    
    status_messages = {
        'accepted': 'Your order has been accepted by the freelancer!',
        'in_progress': 'The freelancer has started working on your order.',
        'submitted': 'The freelancer has submitted the deliverable for your order.',
        'revision_requested': 'The client has requested revisions for your deliverable.',
        'completed': 'Your order has been completed and approved!',
        'cancelled': 'Your order has been cancelled.',
    }
    
    status_message = status_messages.get(status, f'Order status changed to {status}')
    
    message = f"""
Hello {recipient_name},

{status_message}

Order ID: {order.pk}
Gig: {order.gig.title}
Price: ₹{order.price}

Visit your dashboard to view more details.

Best regards,
Hirevo Team
"""
    
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="background-color: white; padding: 30px; border-radius: 5px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Order Status Update</h2>
                <p>Hello {recipient_name},</p>
                <p>{status_message}</p>
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                    <p><strong>Order Details:</strong></p>
                    <p><strong>Order ID:</strong> {order.pk}</p>
                    <p><strong>Gig:</strong> {order.gig.title}</p>
                    <p><strong>Price:</strong> ₹{order.price}</p>
                    <p><strong>Status:</strong> <span style="color: #28a745; font-weight: bold;">{status.upper()}</span></p>
                </div>
                <a href="http://127.0.0.1:8000/orders/{order.pk}/" style="display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 20px 0;">View Order Details</a>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">Best regards,<br><strong>Hirevo Team</strong></p>
            </div>
        </body>
    </html>
    """
    
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [recipient_email],
        html_message=html_message,
        fail_silently=False
    )


def send_delay_notification_email(order, recipient_email, recipient_name, is_freelancer=False):
    """Send email notification when order is delayed"""
    
    subject = f"⚠️ Order Delay Notification - {order.gig.title}"
    
    if is_freelancer:
        message = f"""
Hello {recipient_name},

Your order has exceeded the delivery deadline!

Order ID: {order.pk}
Gig: {order.gig.title}
Deadline: {order.deadline}
Days Delayed: {order.days_delayed() if hasattr(order, 'days_delayed') else 'N/A'}

Please submit your deliverable as soon as possible.

Best regards,
Hirevo Team
"""
    else:
        message = f"""
Hello {recipient_name},

Your order is currently delayed. The freelancer has not submitted the deliverable by the agreed deadline.

Order ID: {order.pk}
Gig: {order.gig.title}
Deadline: {order.deadline}
Days Delayed: {order.days_delayed() if hasattr(order, 'days_delayed') else 'N/A'}

The administrator will be notified and may assign a backup freelancer to help complete your project.

Best regards,
Hirevo Team
"""
    
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="background-color: white; padding: 30px; border-radius: 5px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #d9534f;">⚠️ Order Delay Notification</h2>
                <p>Hello {recipient_name},</p>
                <p>{'Your order has exceeded the delivery deadline!' if is_freelancer else 'Your order is currently delayed. The freelancer has not submitted the deliverable by the agreed deadline.'}</p>
                <div style="background-color: #ffe6e6; padding: 15px; border-left: 4px solid #d9534f; margin: 20px 0;">
                    <p><strong>Order Details:</strong></p>
                    <p><strong>Order ID:</strong> {order.pk}</p>
                    <p><strong>Gig:</strong> {order.gig.title}</p>
                    <p><strong>Deadline:</strong> {order.deadline if hasattr(order, 'deadline') else 'N/A'}</p>
                    <p><strong>Days Delayed:</strong> <span style="color: #d9534f; font-weight: bold;">{order.days_delayed() if hasattr(order, 'days_delayed') else 'N/A'}</span></p>
                </div>
                {'<p>Please submit your deliverable as soon as possible to avoid further penalties.</p>' if is_freelancer else '<p>The administrator will be notified and may assign a backup freelancer to help complete your project.</p>'}
                <a href="http://127.0.0.1:8000/orders/{order.pk}/" style="display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 20px 0;">View Order Details</a>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">Best regards,<br><strong>Hirevo Team</strong></p>
            </div>
        </body>
    </html>
    """
    
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [recipient_email],
        html_message=html_message,
        fail_silently=False
    )


def send_assignment_notification_email(order, freelancer_email, freelancer_name):
    """Send email when a project is assigned to a freelancer"""
    
    subject = f"New Project Assignment - {order.gig.title}"
    
    message = f"""
Hello {freelancer_name},

You have been assigned a new project!

Order ID: {order.pk}
Gig: {order.gig.title}
Price: ₹{order.price}
Client: {order.buyer.username}

Please login to your dashboard to view the project details and start working on it.

Best regards,
Hirevo Team
"""
    
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="background-color: white; padding: 30px; border-radius: 5px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">🎉 New Project Assignment</h2>
                <p>Hello {freelancer_name},</p>
                <p>Congratulations! You have been assigned a new project!</p>
                <div style="background-color: #e8f5e9; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0;">
                    <p><strong>Project Details:</strong></p>
                    <p><strong>Order ID:</strong> {order.pk}</p>
                    <p><strong>Project:</strong> {order.gig.title}</p>
                    <p><strong>Price:</strong> ₹{order.price}</p>
                    <p><strong>Client:</strong> {order.buyer.username if hasattr(order, 'buyer') else 'N/A'}</p>
                </div>
                <a href="http://127.0.0.1:8000/orders/{order.pk}/" style="display: inline-block; background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 20px 0;">View Project Details</a>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">Best regards,<br><strong>Hirevo Team</strong></p>
            </div>
        </body>
    </html>
    """
    
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [freelancer_email],
        html_message=html_message,
        fail_silently=False
    )
