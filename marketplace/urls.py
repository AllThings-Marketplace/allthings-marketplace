from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    # Catalog Discovery
    path('', views.home, name='home'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('service/<slug:slug>/', views.service_detail, name='service_detail'),
    
    # API & Utilities
    path('api/category-attributes/<int:category_id>/', views.get_category_attributes, name='get_category_attributes'),
    
    # Customer Wishlist
    path('saved-items/', views.saved_items_list, name='saved_items'),
    path('api/toggle-save/<int:product_id>/', views.toggle_saved_item, name='toggle_save'),

    # Provider Profile
    path('provider/<int:provider_id>/', views.public_provider_profile, name='public_provider'),
    path('api/toggle-follow/<int:provider_id>/', views.toggle_follow_provider, name='toggle_follow_provider'),
    path('api/provider/<int:provider_id>/inquiry/', views.submit_inquiry, name='submit_inquiry'),
    
    # Unified Inbox (Smart Router for Customers & Providers)
    path('inbox/', views.universal_inbox, name='inbox'),
    
    # Inbox APIs
    path('api/inquiry/<int:inquiry_id>/read/', views.mark_inquiry_read, name='mark_inquiry_read'),
    path('api/inquiry/<int:inquiry_id>/reply/', views.reply_to_inquiry, name='reply_to_inquiry'),

    # "Request What You Need" — Customer Sourcing & Provider Matching
    path('requests/new/', views.create_customer_request, name='create_request'),
    path('requests/my-requests/', views.my_customer_requests, name='my_requests'),
    path('requests/<int:request_id>/', views.customer_request_detail, name='request_detail'),
    path('requests/<int:request_id>/status/', views.update_customer_request_status, name='update_request_status'),
    path('requests/<int:request_id>/match/', views.submit_provider_match, name='submit_provider_match'),

    # Legal, Privacy & Operational Policies
    path('legal/<slug:policy_slug>/', views.legal_policy, name='legal_policy'),
    path('privacy-policy/', views.legal_policy, {'policy_slug': 'privacy-policy'}, name='privacy_policy'),
    path('cookie-policy/', views.legal_policy, {'policy_slug': 'cookie-policy'}, name='cookie_policy'),
    path('terms/', views.legal_policy, {'policy_slug': 'terms-and-conditions'}, name='terms_and_conditions'),
    path('refund-policy/', views.legal_policy, {'policy_slug': 'returns-and-refunds'}, name='refund_policy'),
    path('seller-agreement/', views.legal_policy, {'policy_slug': 'provider-agreement'}, name='provider_agreement'),
]