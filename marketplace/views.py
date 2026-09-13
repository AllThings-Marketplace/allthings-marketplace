from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Count, Prefetch
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from .models import Product, Service, Category, SavedItem, ProductImage, PromoBanner, ProductVariant
from .tasks import process_product_image_task
from feedback.models import Feedback
from .validators import validate_product_image


def home(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')

    # 1. Create a prefetch rule to ONLY grab images that Celery has successfully processed
    approved_images_prefetch = Prefetch(
        'images', # Use your related_name if you defined one (e.g., 'images')
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
    
    # Corrected: Fetch approved images directly from the new model
    gallery_images = ProductImage.objects.filter(product=product, processing_status='APPROVED')
    
    variants = product.variants.all()
    
    # 1. Feedback Data
    feedbacks = Feedback.objects.filter(order_item__product=product)
    avg_rating = feedbacks.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    review_count = feedbacks.count()
    
    # Fetch the actual 5 most recent reviews to display
    recent_reviews = feedbacks.select_related('customer').order_by('-created_at')[:5]
    
    # 2. Recommendation Engine (Same category, excluding current product)
    related_products = Product.objects.filter(
        category=product.category, 
        is_active=True
    ).exclude(id=product.id).order_by('?')[:4] # Randomizes 4 items
    
    context = {
        'product': product,
        'gallery_images': gallery_images,
        'variants': variants,
        'avg_rating': round(avg_rating, 1),
        'review_count': review_count,
        'recent_reviews': recent_reviews,
        'related_products': related_products,
    }
    return render(request, 'product_detail.html', context)

@login_required
def add_product(request):
    profile = getattr(request.user, 'provider_profile', None)
    if not profile or profile.provider_type not in ['VENDOR', 'BOTH']:
        messages.error(request, "Only vendors can add products.")
        return redirect('provider_dashboard')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Secure Category Validation
                category_id = request.POST.get('category_id')
                if not category_id:
                    raise ValidationError("Please select a product category.")
                category = Category.objects.get(id=category_id)

                # 2. Strict Dynamic Attribute Enforcement
                dynamic_attributes = {}
                schema = category.attribute_schema
                
                if schema:
                    for attr in schema:
                        attr_name = attr.get('name', '')
                        is_required = attr.get('required', False)
                        
                        # Recreate the exact HTML input name generated by our JS
                        expected_field_name = f"attr_{attr_name.lower().replace(' ', '_')}"
                        submitted_value = request.POST.get(expected_field_name, '').strip()
                        
                        if is_required and not submitted_value:
                            raise ValidationError(f"The specification '{attr_name}' is required for this category.")
                        
                        if submitted_value:
                            dynamic_attributes[attr_name] = submitted_value

                # 3. Extract and Validate ALL images
                uploaded_files = request.FILES.getlist('images')
                if not uploaded_files:
                    raise ValidationError("You must upload at least one product image.")
                    
                for image_file in uploaded_files:
                    validate_product_image(image_file) 

                # 4. Save the Parent Product 
                product = Product.objects.create(
                    provider=profile,
                    category=category,
                    name=request.POST.get('name'),
                    price=request.POST.get('price'),
                    stock_count=request.POST.get('stock_count', 0),
                    description=request.POST.get('description', ''),
                    attributes=dynamic_attributes, # Safely populated from the schema check
                    status=Product.ProductStatus.PENDING, 
                    is_active=False 
                )

                # 5. Safe Variant Processing & Inventory Sync
                variant_names = request.POST.getlist('variant_names[]')
                variant_values = request.POST.getlist('variant_values[]')
                variant_prices = request.POST.getlist('variant_prices[]')
                variant_stocks = request.POST.getlist('variant_stocks[]')

                has_variants = False
                total_variant_stock = 0

                for name, value, price, stock in zip(variant_names, variant_values, variant_prices, variant_stocks):
                    if name.strip() and value.strip():
                        has_variants = True
                        
                        try:
                            safe_price = Decimal(price.strip()) if price.strip() else None
                        except InvalidOperation:
                            safe_price = None
                            
                        safe_stock = int(stock.strip()) if stock.strip().isdigit() else 0
                        total_variant_stock += safe_stock

                        ProductVariant.objects.create(
                            product=product,
                            attribute_name=name.strip(),
                            attribute_value=value.strip(),
                            price_override=safe_price,
                            stock=safe_stock
                        )

                # 6. Inventory Override
                if has_variants:
                    product.stock_count = total_variant_stock
                    product.save()

                # 7. Save Images and Trigger Celery AI
                for index, image_file in enumerate(uploaded_files):
                    new_image = ProductImage.objects.create(
                        product=product,
                        original_image=image_file,
                        processing_status='UPLOADED',
                        image_type='MAIN' if index == 0 else 'GALLERY'
                    )
                    process_product_image_task.delay(new_image.id)

            messages.success(request, f"Product submitted! {len(uploaded_files)} images are being optimized.")
            return redirect('provider_dashboard')

        except Category.DoesNotExist:
            messages.error(request, "Invalid category selected.")
        except ValidationError as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Upload Error: {error_msg}")
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")

    parent_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    return render(request, 'add_product.html', {'parent_categories': parent_categories})

@login_required
def upload_product_images(request, product_id):
    # 1. Security Check: Ensure the vendor actually owns this product
    profile = getattr(request.user, 'provider_profile', None)
    product = get_object_or_404(Product, id=product_id, provider=profile)

    if request.method == 'POST':
        # Grab all uploaded files from the HTML input (name="images")
        uploaded_files = request.FILES.getlist('images')
        
        if not uploaded_files:
            messages.error(request, "Please select at least one image to upload.")
            return redirect('provider_dashboard')

        for image_file in uploaded_files:
            # 2. Save the raw image to the database instantly
            new_image = ProductImage.objects.create(
                product=product,
                original_image=image_file,
                processing_status='UPLOADED'
            )
            
            # 3. Hand the heavy lifting off to the background worker
            # The .delay() method tells Celery to run this asynchronously
            process_product_image_task.delay(new_image.id)
        
        messages.success(request, f"Successfully uploaded {len(uploaded_files)} image(s). Our system is optimizing them now.")
        return redirect('provider_dashboard')
        
    return render(request, 'marketplace/upload_images.html', {'product': product})

def get_category_attributes(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
        # Returns the JSON list you saved in the Django Admin (e.g., [{"name": "RAM"}])
        return JsonResponse({'schema': category.attribute_schema})
    except Category.DoesNotExist:
        return JsonResponse({'schema': []})

@login_required
def toggle_saved_item(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        
        # Check if the item is already saved
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
    # Fetch all items saved by the current user
    saved_items = SavedItem.objects.filter(user=request.user).select_related('product')
    return render(request, 'saved_items.html', {'saved_items': saved_items})