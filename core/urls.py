from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Your new dedicated vendor command center
    path('dashboard/', include('dashboard.urls')),
    
    # Core Apps
    path('orders/', include('orders.urls')),
    path('accounts/', include('accounts.urls')),
    path('feedback/', include('feedback.urls')),
    
    # The Marketplace catalog acts as the homepage (root)
    path('', include('marketplace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)