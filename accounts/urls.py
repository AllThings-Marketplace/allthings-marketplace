from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_customer, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Provider Onboarding (Not the dashboard!)
    path('apply-provider/', views.apply_provider, name='apply_provider'),
    path('provider-status/', views.provider_status, name='provider_status'),
]