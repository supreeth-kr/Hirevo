from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
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
                    create_notification(
                        user=admin,
                        title="Delayed Project Alert",
                        message=f"Order {order.order_id} ({order.gig.title}) is delayed. Primary freelancer: {order.freelancer.username}. Backup assignment required.",
                        link=f"/admin-dashboard/orders/{order.id}/assign-backup/"
                    )

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
