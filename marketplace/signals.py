"""Django signals for order-related email notifications"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Order, Penalty, BackupAssignment
from .emails import (
    send_order_assigned_email,
    send_order_status_update_email,
    send_order_delayed_email,
    send_backup_assigned_email,
    send_backup_accepted_email
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def order_created_handler(sender, instance, created, **kwargs):
    """
    Send email to freelancer when order is created/assigned.
    Send confirmation email to client when order is placed.
    """
    if created:
        try:
            send_order_assigned_email(instance)
            logger.info(f"Order assignment emails sent for Order {instance.order_id}")
        except Exception as e:
            logger.error(f"Error sending order assignment emails for Order {instance.order_id}: {str(e)}", exc_info=True)


@receiver(pre_save, sender=Order)
def order_status_changed_handler(sender, instance, **kwargs):
    """
    Send email notifications when order status changes.
    - in_progress: Freelancer accepted, notify client
    - rejected: Freelancer declined, notify client
    - submitted: Deliverables submitted, notify client
    - revision_requested: Client requested revision, notify freelancer
    - completed: Client approved, notify freelancer
    """
    if instance.pk:  # Check if this is an update, not creation
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            
            # Check if status has changed
            if old_instance.status != instance.status:
                logger.info(f"Order {instance.order_id} status changed: {old_instance.status} → {instance.status}")
                
                # Send status update emails
                try:
                    send_order_status_update_email(instance, instance.status)
                    logger.info(f"Status update email sent for Order {instance.order_id} (Status: {instance.status})")
                except Exception as e:
                    logger.error(f"Error sending status update email for Order {instance.order_id}: {str(e)}", exc_info=True)
                    
        except Order.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error in order_status_changed_handler: {str(e)}", exc_info=True)


@receiver(post_save, sender=Penalty)
def penalty_created_handler(sender, instance, created, **kwargs):
    """
    Send delay notification email when penalty is applied (order marked as delayed).
    """
    if created and instance.status == 'applied':
        try:
            # Send delay notification emails to both freelancer and client
            send_order_delayed_email(instance.order, instance)
            logger.info(f"Delay notification emails sent for Order {instance.order.order_id}")
        except Exception as e:
            logger.error(f"Error sending delay notification emails for Order {instance.order.order_id}: {str(e)}", exc_info=True)


@receiver(post_save, sender=BackupAssignment)
def backup_assignment_created_handler(sender, instance, created, **kwargs):
    """
    Send email to backup freelancer when assigned.
    Send update email to client when backup is assigned.
    """
    if created and instance.status == 'assigned':
        try:
            send_backup_assigned_email(
                instance.order,
                instance.backup_freelancer,
                instance.assigned_by,
                instance.reason
            )
            logger.info(f"Backup assignment emails sent for Order {instance.order.order_id}")
        except Exception as e:
            logger.error(f"Error sending backup assignment emails for Order {instance.order.order_id}: {str(e)}", exc_info=True)


@receiver(pre_save, sender=BackupAssignment)
def backup_assignment_accepted_handler(sender, instance, **kwargs):
    """
    Send email to client when backup freelancer accepts the assignment.
    """
    if instance.pk:  # Check if this is an update
        try:
            old_instance = BackupAssignment.objects.get(pk=instance.pk)
            
            # Check if status changed from assigned to accepted
            if old_instance.status == 'assigned' and instance.status == 'accepted':
                try:
                    instance.accepted_at = timezone.now()
                    send_backup_accepted_email(instance.order, instance.backup_freelancer)
                    logger.info(f"Backup acceptance email sent for Order {instance.order.order_id}")
                except Exception as e:
                    logger.error(f"Error sending backup acceptance email for Order {instance.order.order_id}: {str(e)}", exc_info=True)
                    
        except BackupAssignment.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error in backup_assignment_accepted_handler: {str(e)}", exc_info=True)
