"""Django signals for order-related email notifications"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Order
from accounts.email_utils import (
    send_order_status_email,
    send_delay_notification_email,
    send_assignment_notification_email
)


@receiver(post_save, sender=Order)
def order_created_signal(sender, instance, created, **kwargs):
    """Send email to freelancer when order is assigned"""
    if created:
        # Send assignment notification to freelancer
        try:
            send_assignment_notification_email(
                order=instance,
                freelancer_email=instance.seller.email,
                freelancer_name=instance.seller.username
            )
        except Exception as e:
            print(f"Error sending order assignment email: {str(e)}")


@receiver(pre_save, sender=Order)
def order_status_changed_signal(sender, instance, **kwargs):
    """Send email to client when order status changes"""
    if instance.pk:  # Check if this is an existing order (update, not create)
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            
            # Check if status has changed
            if old_instance.is_completed != instance.is_completed:
                if instance.is_completed:
                    # Order completed
                    try:
                        send_order_status_email(
                            order=instance,
                            status='completed',
                            recipient_email=instance.buyer.email,
                            recipient_name=instance.buyer.username,
                            is_freelancer=False
                        )
                    except Exception as e:
                        print(f"Error sending order completion email: {str(e)}")
                        
                    # Also notify freelancer
                    try:
                        send_order_status_email(
                            order=instance,
                            status='completed',
                            recipient_email=instance.seller.email,
                            recipient_name=instance.seller.username,
                            is_freelancer=True
                        )
                    except Exception as e:
                        print(f"Error sending order completion email to freelancer: {str(e)}")
        except Order.DoesNotExist:
            pass


def check_and_send_delay_notifications():
    """
    Check for delayed orders and send email notifications.
    This should be called by a management command or celery task
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Find orders that are overdue and not yet delayed
    now = timezone.now()
    overdue_orders = Order.objects.filter(
        is_completed=False,
        payment_intent__isnull=False
    )
    
    for order in overdue_orders:
        # You need to add a deadline field to your Order model
        # For now, we'll calculate based on created_at + a standard delay
        # or use a deadline field if available
        if hasattr(order, 'deadline') and order.deadline and now > order.deadline:
            # Send delay notification to both freelancer and client
            try:
                send_delay_notification_email(
                    order=order,
                    recipient_email=order.seller.email,
                    recipient_name=order.seller.username,
                    is_freelancer=True
                )
            except Exception as e:
                print(f"Error sending delay notification to freelancer: {str(e)}")
            
            try:
                send_delay_notification_email(
                    order=order,
                    recipient_email=order.buyer.email,
                    recipient_name=order.buyer.username,
                    is_freelancer=False
                )
            except Exception as e:
                print(f"Error sending delay notification to client: {str(e)}")
