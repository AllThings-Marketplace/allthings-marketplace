from django.urls import path
from . import views

urlpatterns = [
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('book-service/<int:service_id>/', views.book_service, name='book_service'),
    path('cart/', views.cart_view, name='cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment-verify/', views.verify_payment, name='verify_payment'),
    path('success/<int:order_id>/', views.order_success, name='order_success'),
    path('dashboard/', views.provider_dashboard, name='provider_dashboard'),
    path('accept-job/<int:job_id>/', views.accept_job, name='accept_job'),
    path('update-job/<int:job_id>/<str:new_status>/', views.update_job_status, name='update_job_status'),
    path('history/', views.order_history, name='order_history'),
    path('cart/remove-item/<int:item_id>/', views.remove_item, name='remove_item'),
    path('cart/remove-job/<int:job_id>/', views.remove_job, name='remove_job'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/increase/<int:item_id>/', views.increase_quantity, name='increase_quantity'),
    path('cart/decrease/<int:item_id>/', views.decrease_quantity, name='decrease_quantity'),
    path('order/<int:order_id>/', views.order_details, name='order_details'),
    path('store-orders/', views.vendor_orders, name='vendor_orders'),
    path('update-item/<int:item_id>/<str:new_status>/', views.update_item_status, name='update_item_status'),
    path('confirm-delivery/<int:item_id>/', views.confirm_item_delivery, name='confirm_item_delivery'),
    path('jobs/available/', views.available_jobs, name='available_jobs'),
    path('jobs/accept/<int:job_id>/', views.accept_job, name='accept_job'),
    path('jobs/update-status/<int:job_id>/<str:new_status>/', views.update_job_status, name='update_job_status'),
    path('jobs/verify-completion/<int:job_id>/', views.verify_job_completion, name='verify_job_completion'),
]