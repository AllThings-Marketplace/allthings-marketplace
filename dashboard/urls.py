from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # --- MAIN DASHBOARD ---
    path('', views.provider_dashboard, name='provider_dashboard'),
    
    # --- FINANCIALS ---
    path('request-payout/', views.request_payout, name='request_payout'),

    # --- LISTING MANAGEMENT (Moved from marketplace) ---
    path('add-product/', views.add_product, name='add_product'),
    path('product/<int:product_id>/upload-images/', views.upload_product_images, name='upload_product_images'),
    path('add-service/', views.add_service, name='add_service'),
    path('service/<int:service_id>/edit/', views.edit_service, name='edit_service'),
    path('product/<int:product_id>/edit/', views.edit_product, name='edit_product'),

    # --- VENDOR ORDER MANAGEMENT (Moved from orders) ---
    path('store-orders/', views.vendor_orders, name='vendor_orders'),
    path('update-item/<int:item_id>/<str:new_status>/', views.update_item_status, name='update_item_status'),
    
    # --- SERVICE BOOKING ACTIONS (Moved from orders) ---
    path('service/request/<int:order_id>/accept/', views.accept_service_request, name='accept_service_request'),
    path('service/request/<int:order_id>/decline/', views.decline_service_request, name='decline_service_request'),
    path('service/request/<int:order_id>/start/', views.provider_start_service, name='provider_start_service'),
    path('service/request/<int:order_id>/complete/', views.provider_complete_service, name='provider_complete_service'),
    path('service/request/<int:order_id>/quote/', views.send_quote, name='send_quote'),
]