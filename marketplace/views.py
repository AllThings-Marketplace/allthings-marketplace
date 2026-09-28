import json
from django.shortcuts import redirect, render, get_object_or_404
from django.db.models import Avg, Count, Prefetch
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import (
    Product, Service, Category, SavedItem, ProductImage, 
    PromoBanner, ProviderInquiry
)
from accounts.models import ProviderProfile, Follower
from orders.models import ServiceOrder
from feedback.models import Feedback


def home(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')

    # 1. Create a prefetch rule to ONLY grab images that Celery has successfully processed
    approved_images_prefetch = Prefetch(
        'images', 
        queryset=ProductImage.objects.filter(processing_status='APPROVED')
    )

    # 2. Attach the prefetch to your main product query
    products = Product.objects.filter(is_active=True).annotate(
        avg_rating=Avg('reviews__overall_rating'),
        review_count=Count('reviews')
    ).prefetch_related(approved_images_prefetch)
    
    services = Service.objects.filter(is_active=True)
    categories = Category.objects.filter(is_active=True)
    banners = PromoBanner.objects.filter(is_active=True)
    
    # 3. Attach the prefetch to your recommended products query as well
    recommended = Product.objects.filter(is_active=True).annotate(
        avg_rating=Avg('reviews__overall_rating'),
        review_count=Count('reviews')
    ).prefetch_related(approved_images_prefetch).order_by('?')[:4]

    if category_id:
        try:
            category_id = int(category_id)
            products = products.filter(category_id=category_id)
            services = services.filter(category_id=category_id)
        except ValueError:
            category_id = None

    if query:
        products = products.filter(name__icontains=query)
        services = services.filter(name__icontains=query)
        
    # Fetch Saved Product IDs for the current user's wishlist toggle
    saved_product_ids = []
    if request.user.is_authenticated:
        saved_product_ids = SavedItem.objects.filter(user=request.user).values_list('product_id', flat=True)
        
    context = {
        'products': products,
        'services': services,
        'categories': categories,
        'current_category': category_id,
        'query': query,
        'recommended': recommended,
        'banners': banners, 
        'saved_product_ids': saved_product_ids, 
    }
    return render(request, 'home.html', context)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    gallery_images = ProductImage.objects.filter(product=product, processing_status='APPROVED')
    variants = product.variants.all()
    
    # 1. Feedback Data
    feedbacks = Feedback.objects.filter(order_item__product=product)
    avg_rating = feedbacks.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    review_count = feedbacks.count()
    
    recent_reviews = feedbacks.select_related('customer').order_by('-created_at')[:5]
    
    # 2. Recommendation Engine
    related_products = Product.objects.filter(
        category=product.category, 
        is_active=True
    ).exclude(id=product.id).order_by('?')[:4] 
    
    # 3. Wishlist State
    saved_product_ids = []
    if request.user.is_authenticated:
        saved_product_ids = SavedItem.objects.filter(user=request.user).values_list('product_id', flat=True)
    
    context = {
        'product': product,
        'gallery_images': gallery_images,
        'variants': variants,
        'avg_rating': round(avg_rating, 1),
        'review_count': review_count,
        'recent_reviews': recent_reviews,
        'related_products': related_products,
        'saved_product_ids': saved_product_ids,
    }
    return render(request, 'product_detail.html', context)


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.select_related('provider', 'category'), slug=slug)
    packages = service.packages.all()
    portfolio = service.portfolio_images.all()
    
    # NEW: Fetch Feedback Data for this specific service
    feedbacks = Feedback.objects.filter(service=service, status='APPROVED')
    avg_rating = feedbacks.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    review_count = feedbacks.count()
    
    # Grab the 5 most recent reviews for the feed
    recent_reviews = feedbacks.select_related('customer').prefetch_related('attributes', 'photos').order_by('-created_at')[:5]
    
    context = {
        'service': service,
        'packages': packages,
        'portfolio': portfolio,
        'avg_rating': round(avg_rating, 1),
        'review_count': review_count,
        'recent_reviews': recent_reviews,
    }
    return render(request, 'service_detail.html', context)


def get_category_attributes(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
        return JsonResponse({'schema': category.attribute_schema})
    except Category.DoesNotExist:
        return JsonResponse({'schema': []})


@login_required
def toggle_saved_item(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        
        saved_item = SavedItem.objects.filter(user=request.user, product=product).first()
        
        if saved_item:
            saved_item.delete()
            is_saved = False
            message = "Removed from saved items."
        else:
            SavedItem.objects.create(user=request.user, product=product)
            is_saved = True
            message = "Added to saved items."
            
        return JsonResponse({'is_saved': is_saved, 'message': message})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def saved_items_list(request):
    saved_items = SavedItem.objects.filter(user=request.user).select_related('product')
    return render(request, 'saved_items.html', {'saved_items': saved_items})


def public_provider_profile(request, provider_id):
    # 1. Security: Only fetch the provider if they have passed verification
    provider = get_object_or_404(ProviderProfile, id=provider_id, verification_status='ACTIVE')
    
    # 2. Fetch active services
    services = Service.objects.filter(provider=provider, is_active=True)
    
    # 3. Fetch active products utilizing your existing Celery-approved image prefetch
    approved_images_prefetch = Prefetch(
        'images', 
        queryset=ProductImage.objects.filter(processing_status='APPROVED')
    )
    products = Product.objects.filter(
        provider=provider, 
        is_active=True
    ).prefetch_related(approved_images_prefetch)
    
    # 4. Aggregate real trust metrics from the Feedback model
    reviews = Feedback.objects.filter(
        target_provider=provider.user, 
        status='APPROVED'
    ).select_related('customer').order_by('-created_at')
    
    review_count = reviews.count()
    avg_rating_dict = reviews.aggregate(Avg('overall_rating'))
    rating = round(avg_rating_dict['overall_rating__avg'] or 0, 1)
    
    # 5. Calculate genuine completed jobs (Services that reached the end of the lifecycle)
    total_completed = ServiceOrder.objects.filter(
        provider=provider,
        status__in=['COMPLETED', 'CONFIRMED']
    ).count()

    # 6. Check if the current user is following this provider
    is_following = False
    if request.user.is_authenticated:
        is_following = Follower.objects.filter(user=request.user, provider=provider).exists()
    
    context = {
        'provider': provider,
        'services': services,
        'products': products,
        'reviews': reviews, 
        'review_count': review_count,
        'rating': rating,
        'total_completed': total_completed,
        'is_following': is_following,
    }
    return render(request, 'provider_profile.html', context)


@login_required
def toggle_follow_provider(request, provider_id):
    if request.method == 'POST':
        provider = get_object_or_404(ProviderProfile, id=provider_id)
        
        # get_or_create tries to find the follow record. If it doesn't exist, it creates it.
        follow, created = Follower.objects.get_or_create(user=request.user, provider=provider)
        
        if not created:
            # If it already existed, they are trying to unfollow
            follow.delete()
            is_following = False
            message = f"You unfollowed {provider.business_name}."
        else:
            is_following = True
            message = f"You are now following {provider.business_name}."
            
        return JsonResponse({'is_following': is_following, 'message': message})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def submit_inquiry(request, provider_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_text = data.get('message', '').strip()
            
            if not message_text:
                return JsonResponse({'error': 'Message cannot be empty'}, status=400)
            
            provider = get_object_or_404(ProviderProfile, id=provider_id)
            
            # Save the inquiry to the database
            ProviderInquiry.objects.create(
                sender=request.user,
                provider=provider,
                message=message_text
            )
            
            return JsonResponse({'success': True, 'message': 'Inquiry sent successfully!'})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def universal_inbox(request):
    """
    Acts as a smart router. If the user is a provider, it shows the provider dashboard.
    If they are a customer, it shows the customer dashboard.
    """
    user = request.user
    
    # --- PROVIDER ROUTE ---
    if hasattr(user, 'providerprofile'):
        provider = user.providerprofile
        inquiries = ProviderInquiry.objects.filter(provider=provider).select_related('sender').order_by('-created_at')
        active_orders = ServiceOrder.objects.filter(provider=provider).exclude(
            status__in=['COMPLETED', 'CONFIRMED', 'DECLINED', 'CANCELLED']
        ).select_related('customer', 'service').order_by('-updated_at')
        
        context = {
            'is_provider': True,
            'inquiries': inquiries,
            'unread_count': inquiries.filter(is_read=False).count(),
            'active_orders': active_orders,
        }
        return render(request, 'marketplace/provider_inbox.html', context)
        
    # --- CUSTOMER ROUTE ---
    else:
        # Fetch inquiries the customer has sent to providers
        sent_inquiries = ProviderInquiry.objects.filter(sender=user).select_related('provider').order_by('-created_at')
        
        # Fetch active jobs the customer has booked
        active_orders = ServiceOrder.objects.filter(customer=user).exclude(
            status__in=['COMPLETED', 'CONFIRMED', 'DECLINED', 'CANCELLED']
        ).select_related('provider', 'service').order_by('-updated_at')
        
        context = {
            'is_provider': False,
            'sent_inquiries': sent_inquiries,
            'active_orders': active_orders,
        }
        return render(request, 'marketplace/customer_inbox.html', context)

@login_required
def mark_inquiry_read(request, inquiry_id):
    if request.method == 'POST':
        # Fetch the inquiry and strictly ensure it belongs to the logged-in provider
        inquiry = get_object_or_404(ProviderInquiry, id=inquiry_id, provider__user=request.user)
        
        if not inquiry.is_read:
            inquiry.is_read = True
            inquiry.save(update_fields=['is_read'])
            
        return JsonResponse({'success': True})
        
    return JsonResponse({'error': 'Invalid request method'}, status=405)