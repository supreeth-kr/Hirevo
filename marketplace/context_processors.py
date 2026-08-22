from .models import Notification, Category


def notifications_processor(request):
    """Context processor providing unread notifications and active categories to all templates."""
    context = {
        'nav_categories': Category.objects.filter(is_active=True)[:8],
        'unread_notifications_count': 0,
    }
    if request.user.is_authenticated:
        context['unread_notifications_count'] = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        context['recent_notifications'] = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5]
    return context
