from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('provider/add-product/', views.add_product, name='add_product'),
    path('api/category-attributes/<int:category_id>/', views.get_category_attributes, name='get_category_attributes'),
    path('saved-items/', views.saved_items_list, name='saved_items'),
    path('api/toggle-save/<int:product_id>/', views.toggle_saved_item, name='toggle_save'),
    path('product/<int:product_id>/upload-images/', views.upload_product_images, name='upload_product_images'),
]