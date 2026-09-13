from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.register_customer, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('apply-provider/', views.apply_provider, name='apply_provider'),
    path('provider-status/', views.provider_status, name='provider_status'),
    path('provider-dashboard/', views.provider_dashboard, name='provider_dashboard'),
    path('request-payout/', views.request_payout, name='request_payout'),
]