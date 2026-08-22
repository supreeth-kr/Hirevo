from .models import Notification


def notifications_processor(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications': unread}
    return {'unread_notifications': 0}
