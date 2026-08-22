from django.utils import timezone
from .models import Order, Penalty, Notification, ProjectHistory


def create_notification(user, title, message, link=''):
    Notification.objects.create(user=user, title=title, message=message, link=link)


def add_project_history(order, action, description, performed_by=None):
    ProjectHistory.objects.create(
        order=order, action=action, description=description, performed_by=performed_by
    )


def check_and_apply_delays():
    now = timezone.now()
    active_statuses = ['pending', 'accepted', 'in_progress', 'submitted', 'revision_requested']
    overdue_orders = Order.objects.filter(
        deadline__lt=now,
        status__in=active_statuses
    )
    count = 0
    for order in overdue_orders:
        order.status = Order.STATUS_DELAYED
        order.save(update_fields=['status', 'updated_at'])

        if not hasattr(order, 'penalty'):
            penalty = Penalty.objects.create(
                order=order,
                freelancer=order.freelancer,
                order_amount=order.price,
                percentage=5,
                status=Penalty.STATUS_APPLIED,
            )
            add_project_history(order, 'Delay Detected',
                f'Deadline {order.deadline.strftime("%d %b %Y")} passed. Order marked delayed.',
                performed_by=None)
            add_project_history(order, 'Penalty Applied',
                f'Penalty of ₹{penalty.penalty_amount} (5%) applied to {order.freelancer.username}.',
                performed_by=None)

            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(is_staff=True)
            for admin in admins:
                create_notification(admin, 'Delayed Project',
                    f'Order {order.order_id} is delayed. Assign a backup freelancer.',
                    link=f'/admin-dashboard/delayed/')

            create_notification(order.freelancer, 'Project Delayed',
                f'Your order {order.order_id} has been marked as delayed and a penalty has been applied.',
                link=f'/freelancer/orders/{order.id}/')

            create_notification(order.client, 'Project Delayed',
                f'Your order {order.order_id} has been delayed. Admin has been notified.',
                link=f'/client/orders/{order.id}/')
        count += 1
    return count


def calculate_freelancer_earnings(freelancer):
    from .models import Payment
    completed = Payment.objects.filter(freelancer=freelancer, status='paid')
    total = sum(p.amount for p in completed)
    pending_orders = Order.objects.filter(freelancer=freelancer, status__in=['accepted', 'in_progress', 'submitted'])
    pending = sum(o.price for o in pending_orders)
    return {'total': total, 'pending': pending, 'completed_count': completed.count()}
