from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_customer, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Dedicated "Sell on AllThings" Landing Page
    path('sell/', views.sell_on_allthings, name='sell_on_allthings'),

    # Inline Contact OTP Verification Endpoints (AJAX)
    path('otp/send/', views.send_verification_otp, name='send_otp'),
    path('otp/verify/', views.verify_contact_otp, name='verify_otp'),

    # Provider Onboarding Wizard
    path('apply-provider/', views.apply_provider, name='apply_provider'),
    path('provider-status/', views.provider_status, name='provider_status'),
]