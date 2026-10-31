import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import redirect, render, get_object_or_404
from django.db import transaction
from django.db.models import Avg, Count, Prefetch, Q, F
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import JsonResponse

from .smart_search import parse_search_intent
from .validators import inspect_listing_safety
from .recommender import log_event, get_smart_feed
from .models import (
    Product, Service, Category, SavedItem, ProductImage,
    PromoBanner, ProviderInquiry, CustomerRequest, RequestMatch
)
from accounts.models import ProviderProfile, Follower
from orders.models import ServiceOrder
from feedback.models import Feedback


def _send_platform_notification(recipient_user, notif_type, title, message, target_obj):
    """Safely creates an in-app Bell notification (and triggers Brevo email) for a user."""
    if not recipient_user or not target_obj:
        return
    try:
        from notifications.models import Notification
        ct = ContentType.objects.get_for_model(target_obj)
        Notification.objects.create(
            recipient=recipient_user,
            notification_type=notif_type,
            title=title,
            message=message,
            content_type=ct,
            object_id=target_obj.id,
        )
    except Exception:
        pass


def home(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')

    # Raw Faceted Filter Parameters from Sidebar
    req_min_price = request.GET.get('min_price', '').strip()
    req_max_price = request.GET.get('max_price', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    item_type = request.GET.get('item_type', 'all').strip()  # 'all', 'products', 'services'
    in_stock = request.GET.get('in_stock') == '1'
    sort_by = request.GET.get('sort', '').strip()  # 'newest', 'price_asc', 'price_desc', 'rating'

    # 1. Prefetch only approved images processed by Celery
    approved_images_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(processing_status='APPROVED')
    )

    # 2. Base QuerySets (Approved + Active, ordered newest-first by default)
    base_products_qs = Product.objects.filter(
        is_active=True,
        status=Product.ProductStatus.APPROVED
    ).select_related('category', 'provider').annotate(
        avg_rating=Avg('reviews__overall_rating'),
        review_count=Count('reviews')
    ).prefetch_related(approved_images_prefetch).order_by('-id')

    base_services_qs = Service.objects.filter(
        is_active=True,
        status=Service.ServiceStatus.APPROVED
    ).select_related('provider', 'category').annotate(
        avg_rating=Avg('reviews__overall_rating'),
        review_count=Count('reviews')
    ).order_by('-id')

    products = base_products_qs
    services = base_services_qs

    categories = Category.objects.filter(is_active=True).prefetch_related('subcategories')
    banners = PromoBanner.objects.filter(is_active=True)

    recommended = base_products_qs.order_by('?')[:4]

    # 3. Category Filtering (Includes Parent Category + Direct & Nested Subcategories)
    selected_category_obj = None
    if category_id:
        try:
            category_id = int(category_id)
            selected_category_obj = Category.objects.filter(id=category_id).first()
            category_tree_filter = (
                Q(category_id=category_id) |
                Q(category__parent_id=category_id) |
                Q(category__parent__parent_id=category_id)
            )
            products = products.filter(category_tree_filter)
            services = services.filter(category_tree_filter)
        except ValueError:
            category_id = None

    # Track effective filters (combines NLP extraction + manual sidebar inputs)
    active_min_price = None
    active_max_price = None
    active_location = None

    # 4. Smart NLP Search Engine
    if query:
        intent = parse_search_intent(query)
        clean_query = intent['clean_query']

        if clean_query:
            products = products.filter(
                Q(name__icontains=clean_query) |
                Q(category__name__icontains=clean_query) |
                Q(description__icontains=clean_query)
            )
            services = services.filter(
                Q(name__icontains=clean_query) |
                Q(category__name__icontains=clean_query) |
                Q(description__icontains=clean_query)
            )

        if intent['min_price'] and not req_min_price:
            active_min_price = intent['min_price']
        if intent['max_price'] and not req_max_price:
            active_max_price = intent['max_price']

        if intent['location']:
            active_location = intent['location']
            products = products.filter(
                Q(provider__store_address__icontains=active_location) |
                Q(provider__region__icontains=active_location)
            )
            services = services.filter(
                Q(provider__store_address__icontains=active_location) |
                Q(provider__region__icontains=active_location)
            )

        if intent['is_service_request'] and item_type == 'all':
            item_type = 'services'

    # 5. Manual Sidebar Price Overrides
    if req_min_price:
        try:
            active_min_price = Decimal(req_min_price)
        except InvalidOperation:
            pass

    if req_max_price:
        try:
            active_max_price = Decimal(req_max_price)
        except InvalidOperation:
            pass

    # Apply Unified Price Bounds
    if active_min_price is not None:
        products = products.filter(price__gte=active_min_price)
        services = services.filter(base_price__gte=active_min_price)

    if active_max_price is not None:
        products = products.filter(price__lte=active_max_price)
        services = services.filter(base_price__lte=active_max_price)

    # 6. Minimum Rating Filter
    if min_rating:
        try:
            rating_val = float(min_rating)
            products = products.filter(avg_rating__gte=rating_val)
            services = services.filter(avg_rating__gte=rating_val)
        except ValueError:
            min_rating = ''

    # 7. In-Stock Filter (Products)
    if in_stock:
        products = products.filter(stock_count__gt=0)

    # 8. Item Type Toggle (All vs Products Only vs Services Only)
    if item_type == 'products':
        services = services.none()
    elif item_type == 'services':
        products = products.none()

    # 9. Sorting Engine
    if sort_by == 'price_asc':
        products = products.order_by('price')
        services = services.order_by(F('base_price').asc(nulls_last=True))
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
        services = services.order_by(F('base_price').desc(nulls_last=True))
    elif sort_by == 'rating':
        products = products.order_by(F('avg_rating').desc(nulls_last=True), '-review_count')
        services = services.order_by(F('avg_rating').desc(nulls_last=True), '-review_count')
    elif sort_by == 'newest':
        products = products.order_by('-id')
        services = services.order_by('-id')

    # Determine if we should show the Filtered Catalog view or the Multi-Shelf Smart Homepage
    has_active_filters = any([
        query, category_id, active_min_price is not None,
        active_max_price is not None, min_rating,
        item_type != 'all', in_stock, sort_by
    ])

    # Fetch Saved Product IDs for wishlist hearts
    saved_product_ids = []
    if request.user.is_authenticated:
        saved_product_ids = SavedItem.objects.filter(user=request.user).values_list('product_id', flat=True)

    smart_feed = get_smart_feed(request)

    # 10. Build Rich Homepage Department Shelves (when no filters are active)
    new_arrivals = []
    category_sections = []
    total_product_count = 0
    total_service_count = 0

    if not has_active_filters:
        new_arrivals = list(base_products_qs[:8])
        total_product_count = base_products_qs.count()
        total_service_count = base_services_qs.count()

        parent_product_cats = Category.objects.filter(
            parent__isnull=True,
            is_active=True,
            category_type='PRODUCT'
        )
        for p_cat in parent_product_cats:
            dept_products = list(
                base_products_qs.filter(
                    Q(category=p_cat) |
                    Q(category__parent=p_cat) |
                    Q(category__parent__parent=p_cat)
                )[:4]
            )
            if dept_products:
                category_sections.append({
                    'category': p_cat,
                    'products': dept_products,
                })

    context = {
        'products': products,
        'services': services,
        'new_arrivals': new_arrivals,
        'category_sections': category_sections,
        'total_product_count': total_product_count,
        'total_service_count': total_service_count,
        'categories': categories,
        'current_category': category_id,
        'selected_category_obj': selected_category_obj,
        'query': query,
        'recommended': recommended,
        'banners': banners,
        'saved_product_ids': saved_product_ids,
        'smart_feed': smart_feed,
        # Filter state for UI persistence
        'has_active_filters': has_active_filters,
        'active_min_price': int(active_min_price) if active_min_price is not None else '',
        'active_max_price': int(active_max_price) if active_max_price is not None else '',
        'active_location': active_location,
        'min_rating': min_rating,
        'item_type': item_type,
        'in_stock': in_stock,
        'sort_by': sort_by,
    }
    return render(request, 'marketplace/home.html', context)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)

    log_event(request, product, 'VIEW')

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
        is_active=True,
        status=Product.ProductStatus.APPROVED
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
    return render(request, 'marketplace/product_detail.html', context)


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.select_related('provider', 'category'), slug=slug)

    log_event(request, service, 'VIEW')

    packages = service.packages.all()
    portfolio = service.portfolio_images.all()

    feedbacks = Feedback.objects.filter(service=service, status='APPROVED')
    avg_rating = feedbacks.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    review_count = feedbacks.count()

    recent_reviews = feedbacks.select_related('customer').prefetch_related('attributes', 'photos').order_by('-created_at')[:5]

    context = {
        'service': service,
        'packages': packages,
        'portfolio': portfolio,
        'avg_rating': round(avg_rating, 1),
        'review_count': review_count,
        'recent_reviews': recent_reviews,
    }
    return render(request, 'marketplace/service_detail.html', context)


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
    approved_images_prefetch = Prefetch(
        'product__images',
        queryset=ProductImage.objects.filter(processing_status='APPROVED')
    )
    saved_items = (
        SavedItem.objects.filter(user=request.user)
        .select_related('product', 'product__category', 'product__provider')
        .prefetch_related(approved_images_prefetch)
    )
    return render(request, 'marketplace/saved_items.html', {'saved_items': saved_items})


def public_provider_profile(request, provider_id):
    provider = get_object_or_404(ProviderProfile, id=provider_id, verification_status='ACTIVE')

    services = Service.objects.filter(
        provider=provider,
        is_active=True,
        status=Service.ServiceStatus.APPROVED
    ).order_by('-id')

    approved_images_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(processing_status='APPROVED')
    )
    products = Product.objects.filter(
        provider=provider,
        is_active=True,
        status=Product.ProductStatus.APPROVED
    ).prefetch_related(approved_images_prefetch).order_by('-id')

    reviews = Feedback.objects.filter(
        target_provider=provider.user,
        status='APPROVED'
    ).select_related('customer').order_by('-created_at')

    review_count = reviews.count()
    avg_rating_dict = reviews.aggregate(Avg('overall_rating'))
    rating = round(avg_rating_dict['overall_rating__avg'] or 0, 1)

    total_completed = ServiceOrder.objects.filter(
        provider=provider,
        status__in=['COMPLETED', 'CONFIRMED']
    ).count()

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
    return render(request, 'marketplace/provider_profile.html', context)


@login_required
def toggle_follow_provider(request, provider_id):
    if request.method == 'POST':
        provider = get_object_or_404(ProviderProfile, id=provider_id)
        follow, created = Follower.objects.get_or_create(user=request.user, provider=provider)

        if not created:
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

            inquiry = ProviderInquiry.objects.create(
                sender=request.user,
                provider=provider,
                message=message_text
            )

            if provider.user and provider.user != request.user:
                snippet = (message_text[:60] + '...') if len(message_text) > 60 else message_text
                _send_platform_notification(
                    recipient_user=provider.user,
                    notif_type='INQUIRY',
                    title=f"New Inquiry from {request.user.username}",
                    message=f"\"{snippet}\"",
                    target_obj=inquiry,
                )

            return JsonResponse({'success': True, 'message': 'Inquiry sent successfully!'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def universal_inbox(request):
    """
    Acts as a smart router. If the user is a provider, it shows the provider inbox.
    If they are a customer, it shows the customer inbox.
    """
    user = request.user

    # --- PROVIDER ROUTE ---
    if hasattr(user, 'provider_profile'):
        provider = user.provider_profile
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
        sent_inquiries = ProviderInquiry.objects.filter(sender=user).select_related('provider').order_by('-created_at')
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
        inquiry = get_object_or_404(ProviderInquiry, id=inquiry_id, provider__user=request.user)

        if not inquiry.is_read:
            inquiry.is_read = True
            inquiry.save(update_fields=['is_read'])

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request method'}, status=405)


# ==============================================================================
# "REQUEST WHAT YOU NEED" — SOURCING, MATCHING & PROVIDER LEAD ENGINE
# ==============================================================================

def _run_instant_catalog_matching(customer_request):
    """
    Stage 2: Searches existing approved listings for relevant matches right when
    a CustomerRequest is created and saves up to 6 instant suggestions.
    """
    keywords = [
        w.strip() for w in customer_request.title.split()
        if len(w.strip()) >= 3
    ]
    if customer_request.brand:
        keywords.append(customer_request.brand.strip())

    keyword_q = Q()
    for word in keywords[:5]:
        keyword_q |= Q(name__icontains=word) | Q(description__icontains=word)

    cat = customer_request.category
    cat_q = Q()
    if cat:
        cat_q = Q(category=cat) | Q(category__parent=cat)
        if cat.parent_id:
            cat_q |= Q(category_id=cat.parent_id)

    matches_created = 0

    if customer_request.request_type == CustomerRequest.RequestType.PRODUCT:
        qs = Product.objects.filter(
            is_active=True,
            status=Product.ProductStatus.APPROVED,
            stock_count__gt=0
        ).select_related('provider', 'category')

        if keyword_q and cat_q:
            candidates = list(qs.filter(keyword_q | cat_q).distinct()[:6])
        elif keyword_q:
            candidates = list(qs.filter(keyword_q).distinct()[:6])
        elif cat_q:
            candidates = list(qs.filter(cat_q).distinct()[:6])
        else:
            candidates = []

        for prod in candidates:
            RequestMatch.objects.get_or_create(
                customer_request=customer_request,
                product=prod,
                defaults={
                    'provider': prod.provider,
                    'match_source': RequestMatch.MatchSource.SYSTEM,
                    'quoted_price': prod.price,
                    'note': 'Instant catalog match based on your request.',
                }
            )
            matches_created += 1

    else:
        qs = Service.objects.filter(
            is_active=True,
            status=Service.ServiceStatus.APPROVED
        ).select_related('provider', 'category')

        if keyword_q and cat_q:
            candidates = list(qs.filter(keyword_q | cat_q).distinct()[:6])
        elif keyword_q:
            candidates = list(qs.filter(keyword_q).distinct()[:6])
        elif cat_q:
            candidates = list(qs.filter(cat_q).distinct()[:6])
        else:
            candidates = []

        for srv in candidates:
            RequestMatch.objects.get_or_create(
                customer_request=customer_request,
                service=srv,
                defaults={
                    'provider': srv.provider,
                    'match_source': RequestMatch.MatchSource.SYSTEM,
                    'quoted_price': srv.base_price,
                    'note': f"Verified {srv.category.name} professional in {srv.provider.region or 'Nigeria'}.",
                }
            )
            matches_created += 1

    if matches_created > 0:
        customer_request.status = CustomerRequest.RequestStatus.MATCHED
    else:
        customer_request.status = CustomerRequest.RequestStatus.MATCHING
    customer_request.save(update_fields=['status'])
    return matches_created


def _notify_relevant_providers(customer_request):
    """
    Stage 3: Notifies relevant ACTIVE vendors or service professionals (filtered
    by provider_type and region/category) without spamming unrelated stores.
    """
    if customer_request.request_type == CustomerRequest.RequestType.PRODUCT:
        allowed_types = ['VENDOR', 'BOTH']
    else:
        allowed_types = ['SERVICE', 'BOTH']

    providers_qs = ProviderProfile.objects.filter(
        verification_status='ACTIVE',
        provider_type__in=allowed_types
    ).exclude(user=customer_request.customer).select_related('user')

    if customer_request.region:
        regional = list(providers_qs.filter(region__icontains=customer_request.region)[:10])
    else:
        regional = []

    target_providers = regional if regional else list(providers_qs[:10])

    for prov in target_providers:
        _send_platform_notification(
            recipient_user=prov.user,
            notif_type='INQUIRY',
            title=f"New Buyer Request: {customer_request.title[:35]}",
            message=f"A customer in {customer_request.region} is looking for '{customer_request.title}'. Click to respond with a matching listing.",
            target_obj=customer_request,
        )


@login_required
def create_customer_request(request):
    """
    Renders and processes the 'Request What You Need' form for both Products and Services.
    Automatically pre-populates ?q= from the search bar and ?type=PRODUCT|SERVICE.
    """
    initial_query = request.GET.get('q', '').strip()
    initial_type = request.GET.get('type', 'PRODUCT').upper().strip()
    if initial_type not in ['PRODUCT', 'SERVICE']:
        initial_type = 'PRODUCT'

    product_categories = Category.objects.filter(is_active=True, category_type='PRODUCT').order_by('name')
    service_categories = Category.objects.filter(is_active=True, category_type='SERVICE').order_by('name')

    if request.method == 'POST':
        req_type = request.POST.get('request_type', 'PRODUCT').upper().strip()
        if req_type not in ['PRODUCT', 'SERVICE']:
            req_type = 'PRODUCT'
        initial_type = req_type

        title = request.POST.get('title', '').strip()
        category_id = request.POST.get('category_id')
        brand = request.POST.get('brand', '').strip()

        # Safely resolve specifications from either the active input or list of inputs
        spec_values = [s.strip() for s in request.POST.getlist('specifications') if s.strip()]
        specifications = spec_values[0] if spec_values else ''

        condition = request.POST.get('condition', 'NEW').strip()
        region = request.POST.get('region', 'Rivers State').strip()
        location_detail = request.POST.get('location_detail', '').strip()
        preferred_date_raw = request.POST.get('preferred_date', '').strip()
        description = request.POST.get('description', '').strip()

        budget_min_raw = request.POST.get('budget_min', '').strip()
        budget_max_raw = request.POST.get('budget_max', '').strip()

        try:
            if not title:
                raise ValidationError("Please enter the name of the product or service you need.")

            # Anti-leakage check so phone numbers / bank accounts are never posted publicly
            safety_result = inspect_listing_safety(
                title=title,
                description=description or "Customer sourcing request details",
                extra_texts=[brand, specifications, location_detail]
            )
            if isinstance(safety_result, tuple) and safety_result[0]:
                raise ValidationError(safety_result[1])

            budget_min = Decimal(budget_min_raw) if budget_min_raw else None
            budget_max = Decimal(budget_max_raw) if budget_max_raw else None
            if budget_min is not None and budget_min < 0:
                raise ValidationError("Minimum budget cannot be negative.")
            if budget_max is not None and budget_max < 0:
                raise ValidationError("Maximum budget cannot be negative.")
            if budget_min is not None and budget_max is not None and budget_min > budget_max:
                raise ValidationError("Minimum budget cannot be greater than maximum budget.")

            category_obj = Category.objects.filter(id=category_id).first() if category_id else None

            with transaction.atomic():
                new_req = CustomerRequest.objects.create(
                    customer=request.user,
                    request_type=req_type,
                    title=title,
                    category=category_obj,
                    brand=brand if req_type == 'PRODUCT' else '',
                    specifications=specifications,
                    condition=condition if req_type == 'PRODUCT' else 'ANY',
                    budget_min=budget_min,
                    budget_max=budget_max,
                    region=region or 'Rivers State',
                    location_detail=location_detail,
                    preferred_date=preferred_date_raw if (req_type == 'SERVICE' and preferred_date_raw) else None,
                    description=description,
                )

                instant_count = _run_instant_catalog_matching(new_req)
                _notify_relevant_providers(new_req)

            if instant_count > 0:
                messages.success(
                    request,
                    f"Request {new_req.reference} submitted! We found {instant_count} similar listing(s) in our catalog and alerted verified providers."
                )
            else:
                messages.success(
                    request,
                    f"Request {new_req.reference} submitted! We have notified verified AllThings providers who specialize in this department."
                )
            return redirect('marketplace:request_detail', request_id=new_req.id)

        except (ValidationError, InvalidOperation) as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            messages.error(request, error_msg)

    context = {
        'initial_query': initial_query,
        'initial_type': initial_type,
        'product_categories': product_categories,
        'service_categories': service_categories,
    }
    return render(request, 'marketplace/request_form.html', context)


@login_required
def my_customer_requests(request):
    """
    Customer's 'My Requests' dashboard + Open Buyer Requests board for ACTIVE providers.
    """
    my_requests = CustomerRequest.objects.filter(
        customer=request.user
    ).select_related('category').annotate(
        match_count=Count('matches')
    ).order_by('-created_at')

    is_active_provider = (
        hasattr(request.user, 'provider_profile')
        and request.user.provider_profile.verification_status == 'ACTIVE'
    )
    open_buyer_requests = []
    if is_active_provider:
        profile = request.user.provider_profile
        open_qs = CustomerRequest.objects.filter(
            status__in=['PENDING', 'MATCHING', 'MATCHED']
        ).exclude(customer=request.user).select_related('category', 'customer')

        if profile.provider_type == 'VENDOR':
            open_qs = open_qs.filter(request_type='PRODUCT')
        elif profile.provider_type == 'SERVICE':
            open_qs = open_qs.filter(request_type='SERVICE')

        open_buyer_requests = list(open_qs.annotate(match_count=Count('matches'))[:20])

    context = {
        'my_requests': my_requests,
        'is_active_provider': is_active_provider,
        'open_buyer_requests': open_buyer_requests,
    }
    return render(request, 'marketplace/my_requests.html', context)


@login_required
def customer_request_detail(request, request_id):
    """
    Displays a CustomerRequest, its Instant & Provider Matches, and allows:
    - The Customer to review matches, click through to buy/book via Escrow, or mark Fulfilled/Cancelled.
    - An ACTIVE Provider to pitch one of their approved Products or Services to fulfill the request.
    """
    cust_request = get_object_or_404(
        CustomerRequest.objects.select_related('customer', 'category'),
        id=request_id
    )

    is_owner = (cust_request.customer == request.user)
    provider_profile = getattr(request.user, 'provider_profile', None)
    is_active_provider = bool(provider_profile and provider_profile.verification_status == 'ACTIVE')

    if not (is_owner or is_active_provider or request.user.is_staff):
        messages.error(request, "You do not have permission to view that request.")
        return redirect('marketplace:my_requests')

    matches = cust_request.matches.select_related(
        'provider', 'product', 'service', 'product__category', 'service__category'
    ).order_by('match_source', '-created_at')

    provider_products = []
    provider_services = []
    if is_active_provider and not is_owner:
        if cust_request.request_type == 'PRODUCT':
            provider_products = Product.objects.filter(
                provider=provider_profile,
                is_active=True,
                status=Product.ProductStatus.APPROVED
            )
        else:
            provider_services = Service.objects.filter(
                provider=provider_profile,
                is_active=True,
                status=Service.ServiceStatus.APPROVED
            )

    context = {
        'cust_request': cust_request,
        'matches': matches,
        'is_owner': is_owner,
        'is_active_provider': is_active_provider,
        'provider_products': provider_products,
        'provider_services': provider_services,
    }
    return render(request, 'marketplace/request_detail.html', context)


@login_required
def update_customer_request_status(request, request_id):
    """Allows the customer who created the request to mark it FULFILLED or CANCELLED."""
    if request.method == 'POST':
        cust_request = get_object_or_404(CustomerRequest, id=request_id, customer=request.user)
        new_status = request.POST.get('status', '').upper().strip()
        if new_status in ['FULFILLED', 'CANCELLED']:
            cust_request.status = new_status
            cust_request.save(update_fields=['status', 'updated_at'])
            messages.success(request, f"Request {cust_request.reference} marked as {cust_request.get_status_display()}.")
    return redirect('marketplace:request_detail', request_id=request_id)


@login_required
def submit_provider_match(request, request_id):
    """
    Allows an ACTIVE provider to respond to a CustomerRequest by attaching one of their
    approved Products or Services, which notifies the customer immediately.
    """
    provider_profile = getattr(request.user, 'provider_profile', None)
    if not provider_profile or provider_profile.verification_status != 'ACTIVE':
        messages.error(request, "Only verified active providers can submit matches.")
        return redirect('marketplace:home')

    cust_request = get_object_or_404(CustomerRequest, id=request_id)
    if cust_request.customer == request.user:
        messages.error(request, "You cannot submit a match to your own request.")
        return redirect('marketplace:request_detail', request_id=request_id)

    if request.method == 'POST':
        listing_id = request.POST.get('listing_id')
        quoted_price_raw = request.POST.get('quoted_price', '').strip()
        note = request.POST.get('note', '').strip()

        try:
            if note:
                safety_result = inspect_listing_safety(
                    title=cust_request.title,
                    description=note,
                    provider=provider_profile
                )
                if isinstance(safety_result, tuple) and safety_result[0]:
                    raise ValidationError(safety_result[1])

            quoted_price = Decimal(quoted_price_raw) if quoted_price_raw else None

            if cust_request.request_type == 'PRODUCT':
                prod = get_object_or_404(
                    Product,
                    id=listing_id,
                    provider=provider_profile,
                    status=Product.ProductStatus.APPROVED
                )
                RequestMatch.objects.update_or_create(
                    customer_request=cust_request,
                    product=prod,
                    defaults={
                        'provider': provider_profile,
                        'match_source': RequestMatch.MatchSource.PROVIDER,
                        'quoted_price': quoted_price or prod.price,
                        'note': note or f"Available in stock from {provider_profile.business_name}.",
                    }
                )
            else:
                srv = get_object_or_404(
                    Service,
                    id=listing_id,
                    provider=provider_profile,
                    status=Service.ServiceStatus.APPROVED
                )
                RequestMatch.objects.update_or_create(
                    customer_request=cust_request,
                    service=srv,
                    defaults={
                        'provider': provider_profile,
                        'match_source': RequestMatch.MatchSource.PROVIDER,
                        'quoted_price': quoted_price or srv.base_price,
                        'note': note or f"Ready to handle your project — {provider_profile.business_name}.",
                    }
                )

            cust_request.status = CustomerRequest.RequestStatus.MATCHED
            cust_request.save(update_fields=['status', 'updated_at'])

            _send_platform_notification(
                recipient_user=cust_request.customer,
                notif_type='ORDER',
                title=f"Match Found for {cust_request.reference}!",
                message=f"{provider_profile.business_name} responded to your request for '{cust_request.title}'. View the listing now.",
                target_obj=cust_request,
            )

            messages.success(request, "Your listing has been sent to the customer!")
        except (ValidationError, InvalidOperation) as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            messages.error(request, error_msg)

    return redirect('marketplace:request_detail', request_id=request_id)