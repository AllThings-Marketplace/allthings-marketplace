from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Notification

@login_required
def notification_history(request):
    # Fetch all notifications for this user, ordered by newest first
    notifications = Notification.objects.filter(recipient=request.user)
    
    context = {
        'notifications': notifications,
    }
    return render(request, 'notifications/history.html', context)

@login_required
def mark_all_read(request):
    # Update all unread notifications for this user in a single database hit
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    # Redirect back to the page they came from (either history or home)
    next_url = request.META.get('HTTP_REFERER', 'marketplace:home')
    return redirect(next_url)