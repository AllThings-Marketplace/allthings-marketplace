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
    path('provider/<int:provider_id>/', views.provider_storefront, name='provider_storefront'),
]