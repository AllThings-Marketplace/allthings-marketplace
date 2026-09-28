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
]