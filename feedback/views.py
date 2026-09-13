from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from orders.models import OrderItem, JobBooking
from .models import Feedback, FeedbackAttribute

@login_required
def product_feedback_view(request, item_id):
    # 1. Verify ownership and ensure the item belongs to the customer
    item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
    
    # 2. Prevent duplicate reviews
    if hasattr(item, 'feedback'):
        messages.info(request, "You have already reviewed this product.")
        return redirect('home')

    if request.method == 'POST':
        # 3. Handle the relationship bridge
        # Product points to ProviderProfile. We add .user to get the base account.
        target_user = item.product.provider.user 
        
        feedback = Feedback.objects.create(
            customer=request.user,
            target_provider=target_user,
            transaction_type=Feedback.TransactionType.PRODUCT,
            order_item=item,
            product=item.product,  # --- NEW: Direct Product Link ---
            overall_rating=request.POST.get('overall_rating', 5),
            public_review=request.POST.get('public_review', ''),
            private_feedback=request.POST.get('private_feedback', ''),
            is_verified=True
        )
        
        # 4. Save the product-specific dynamic attributes
        attributes = {
            'Product Quality': request.POST.get('attr_quality', 5),
            'As Described': request.POST.get('attr_described', 5),
            'Delivery Experience': request.POST.get('attr_delivery', 5)
        }
        
        for name, rating in attributes.items():
            if rating: 
                FeedbackAttribute.objects.create(feedback=feedback, attribute_name=name, rating=rating)
            
        messages.success(request, "Thank you for your feedback!")
        return redirect('home')
        
    return render(request, 'feedback/product_form.html', {'item': item})


@login_required
def service_feedback_view(request, job_id):
    job = get_object_or_404(JobBooking, id=job_id, order__customer=request.user)
    
    if hasattr(job, 'feedback'):
        messages.info(request, "You have already reviewed this service.")
        return redirect('home')

    if request.method == 'POST':
        # JobBooking points directly to the User model, so no conversion is needed.
        target_user = job.provider 
        
        feedback = Feedback.objects.create(
            customer=request.user,
            target_provider=target_user, 
            transaction_type=Feedback.TransactionType.SERVICE,
            job_booking=job,
            service=job.service,  # --- NEW: Direct Service Link ---
            overall_rating=request.POST.get('overall_rating', 5),
            public_review=request.POST.get('public_review', ''),
            private_feedback=request.POST.get('private_feedback', ''),
            is_verified=True
        )
        
        # Save the service-specific dynamic attributes
        attributes = {
            'Professionalism': request.POST.get('attr_professionalism', 5),
            'Quality of Work': request.POST.get('attr_quality', 5),
            'Punctuality': request.POST.get('attr_punctuality', 5),
            'Communication': request.POST.get('attr_communication', 5)
        }
        
        for name, rating in attributes.items():
            if rating:
                FeedbackAttribute.objects.create(feedback=feedback, attribute_name=name, rating=rating)
            
        messages.success(request, "Thank you for your feedback!")
        return redirect('home')

    return render(request, 'feedback/service_form.html', {'job': job})

@login_required
def pending_reviews_list(request):
    # 1. Fetch unreviewed products that have actually been delivered
    pending_products = OrderItem.objects.filter(
        order__customer=request.user,
        feedback__isnull=True,
        status__in=['DELIVERED', 'COMPLETED'] 
    ).select_related('product')
    
    # 2. Fetch unreviewed services that are fully finished
    pending_services = JobBooking.objects.filter(
        order__customer=request.user,
        feedback__isnull=True,
        status='COMPLETED'
    ).select_related('service')
    
    context = {
        'pending_products': pending_products,
        'pending_services': pending_services,
    }
    return render(request, 'feedback/pending_reviews.html', context)