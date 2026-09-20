from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # 1. Product Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove-item/<int:item_id>/', views.remove_item, name='remove_item'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/increase/<int:item_id>/', views.increase_quantity, name='increase_quantity'),
    path('cart/decrease/<int:item_id>/', views.decrease_quantity, name='decrease_quantity'),

    # 2. Service Booking
    path('service/<int:service_id>/book/', views.process_service_booking, name='process_service_booking'),
    path('service/booking/success/<str:reference>/', views.service_booking_success, name='service_booking_success'),
    path('service/checkout/<int:order_id>/', views.service_checkout, name='service_checkout'),

    # 3. Checkout & Payment
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment-verify/', views.verify_payment, name='verify_payment'),
    path('webhook/paystack/', views.paystack_webhook, name='paystack_webhook'),

    # 4. Customer Order History & Actions
    path('success/<int:order_id>/', views.order_success, name='order_success'),
    path('history/', views.order_history, name='order_history'),
    path('order/<int:order_id>/', views.order_details, name='order_details'),
    path('confirm-delivery/<int:item_id>/', views.confirm_item_delivery, name='confirm_item_delivery'),
    path('service/request/<int:order_id>/confirm/', views.customer_confirm_service, name='customer_confirm_service'),
    path('service/checkout/<int:order_id>/reject-quote/', views.reject_quote, name='reject_quote'),
    path('service/<int:order_id>/message/', views.send_order_message, name='send_order_message'),
    path('service/<int:order_id>/chat/', views.order_chat, name='order_chat'),
    path('service/<int:order_id>/report-problem/', views.report_dispute, name='report_dispute'),
]