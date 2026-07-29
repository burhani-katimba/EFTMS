from .models import Notification


def notifications_processor(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        recent_notifs = Notification.objects.filter(
            recipient=request.user
        ).order_by("-created_at")[:5]
        return {
            "unread_notifications_count": unread_count,
            "recent_notifications": recent_notifs,
        }
    return {}
