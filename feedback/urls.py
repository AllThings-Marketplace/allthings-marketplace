from django.urls import path
from . import views

app_name = 'feedback'

urlpatterns = [
    path('review/product/<int:item_id>/', views.product_feedback_view, name='product_feedback'),
    path('review/service/<int:service_order_id>/', views.service_feedback_view, name='service_feedback'),
    path('pending-reviews/', views.pending_reviews_list, name='pending_reviews'),
]