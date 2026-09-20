from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from orders.models import OrderItem, ServiceOrder
from .models import Feedback, FeedbackAttribute, FeedbackPhoto

@login_required
def product_feedback_view(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
    
    if hasattr(item, 'feedback'):
        messages.info(request, "You have already reviewed this product.")
        return redirect('orders:order_history')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                feedback = Feedback.objects.create(
                    customer=request.user,
                    target_provider=item.product.provider.user,
                    transaction_type=Feedback.TransactionType.PRODUCT,
                    order_item=item,
                    product=item.product,
                    overall_rating=request.POST.get('overall_rating', 5),
                    public_review=request.POST.get('public_review', ''),
                    private_feedback=request.POST.get('private_feedback', ''),
                    is_verified=True
                )
                
                attributes = {
                    'Product Quality': request.POST.get('attr_quality', 5),
                    'As Described': request.POST.get('attr_described', 5),
                    'Delivery Experience': request.POST.get('attr_delivery', 5)
                }
                
                for name, rating in attributes.items():
                    if rating: 
                        FeedbackAttribute.objects.create(feedback=feedback, attribute_name=name, rating=rating)
                
                # Handle optional photo upload
                photo = request.FILES.get('feedback_photo')
                if photo:
                    FeedbackPhoto.objects.create(feedback=feedback, image=photo)
                    
            messages.success(request, "Thank you for your feedback!")
            return redirect('orders:order_history')
            
        except Exception as e:
            messages.error(request, f"Error saving review: {str(e)}")
        
    return render(request, 'feedback/product_form.html', {'item': item})


@login_required
def service_feedback_view(request, service_order_id):
    # Ensure they can only review CONFIRMED jobs
    service_order = get_object_or_404(ServiceOrder, id=service_order_id, customer=request.user, status='CONFIRMED')
    
    if hasattr(service_order, 'feedback'):
        messages.info(request, "You have already reviewed this service.")
        return redirect('orders:order_history')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                feedback = Feedback.objects.create(
                    customer=request.user,
                    target_provider=service_order.provider.user, 
                    transaction_type=Feedback.TransactionType.SERVICE,
                    service_order=service_order,
                    service=service_order.service,
                    overall_rating=request.POST.get('overall_rating', 5),
                    public_review=request.POST.get('public_review', ''),
                    private_feedback=request.POST.get('private_feedback', ''),
                    is_verified=True
                )
                
                attributes = {
                    'Professionalism': request.POST.get('attr_professionalism', 5),
                    'Quality of Work': request.POST.get('attr_quality', 5),
                    'Punctuality': request.POST.get('attr_punctuality', 5),
                    'Communication': request.POST.get('attr_communication', 5)
                }
                
                for name, rating in attributes.items():
                    if rating:
                        FeedbackAttribute.objects.create(feedback=feedback, attribute_name=name, rating=rating)
                        
                # Handle optional photo upload
                photo = request.FILES.get('feedback_photo')
                if photo:
                    FeedbackPhoto.objects.create(feedback=feedback, image=photo)
                    
            messages.success(request, "Thank you for your feedback!")
            return redirect('orders:order_history')
            
        except Exception as e:
            messages.error(request, f"Error saving review: {str(e)}")

    return render(request, 'feedback/service_form.html', {'job': service_order})

@login_required
def pending_reviews_list(request):
    pending_products = OrderItem.objects.filter(
        order__customer=request.user,
        feedback__isnull=True,
        status__in=['DELIVERED', 'COMPLETED'] 
    ).select_related('product')
    
    # Updated to strictly require 'CONFIRMED' status
    pending_services = ServiceOrder.objects.filter(
        customer=request.user,
        feedback__isnull=True,
        status='CONFIRMED'
    ).select_related('service')
    
    context = {
        'pending_products': pending_products,
        'pending_services': pending_services,
    }
    return render(request, 'feedback/pending_reviews.html', context)