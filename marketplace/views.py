from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Count, Prefetch
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import (
    Product, Service, Category, SavedItem, ProductImage, 
    PromoBanner, ProductVariant, ServicePackage, ServiceImage
)
from accounts.models import ProviderProfile
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

def provider_storefront(request, provider_id):
    # Fetch the provider's public profile
    provider = get_object_or_404(ProviderProfile, id=provider_id)
    
    # Fetch their active catalog
    services = Service.objects.filter(provider=provider, is_active=True)
    products = Product.objects.filter(provider=provider, status='APPROVED')
    
    # Fetch all approved reviews for this provider
    reviews = Feedback.objects.filter(target_provider=provider.user, status='APPROVED').order_by('-created_at')
    
    # Calculate lifetime trust metrics
    review_count = reviews.count()
    avg_rating_dict = reviews.aggregate(Avg('overall_rating'))
    avg_rating = round(avg_rating_dict['overall_rating__avg'] or 0, 1)
    
    context = {
        'provider': provider,
        'services': services,
        'products': products,
        'reviews': reviews,
        'review_count': review_count,
        'avg_rating': avg_rating,
    }
    return render(request, 'provider_storefront.html', context)