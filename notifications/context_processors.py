from .models import Notification

def global_notifications(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        recent_alerts = Notification.objects.filter(recipient=request.user)[:5] # Grab the 5 latest
        return {
            'global_unread_count': unread_count,
            'global_recent_notifications': recent_alerts
        }
    return {
        'global_unread_count': 0,
        'global_recent_notifications': []
    }