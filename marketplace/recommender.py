import json
from urllib.parse import unquote
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count, Prefetch
from .models import UserInteraction, Product, Service, ProductImage

CONSENT_COOKIE_NAME = 'allthings_cookie_consent'


def get_cookie_consent(request):
    """
    Parses the first-party 'allthings_cookie_consent' cookie.
    Defaults:
      - necessary: True (always active)
      - functional: False until accepted
      - analytics: False until accepted
      - marketing: False until accepted
    """
    raw_cookie = request.COOKIES.get(CONSENT_COOKIE_NAME)
    if not raw_cookie:
        return {
            'has_decided': False,
            'necessary': True,
            'functional': False,
            'analytics': False,
            'marketing': False,
        }
    try:
        parsed = json.loads(unquote(raw_cookie))
        return {
            'has_decided': True,
            'necessary': True,
            'functional': bool(parsed.get('functional', False)),
            'analytics': bool(parsed.get('analytics', False)),
            'marketing': bool(parsed.get('marketing', False)),
        }
    except Exception:
        return {
            'has_decided': False,
            'necessary': True,
            'functional': False,
            'analytics': False,
            'marketing': False,
        }


def has_analytics_consent(request):
    """
    Returns True if the user has accepted Analytics & Smart Recommendations cookies.
    """
    consent = get_cookie_consent(request)
    return consent['analytics']


def _get_approved_products_base_qs():
    """
    Returns approved, active products with prefetched studio images and ratings
    so recommendation shelves match the main catalog cards with zero N+1 queries.
    """
    approved_images_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(processing_status='APPROVED')
    )
    return (
        Product.objects.filter(
            is_active=True,
            status=Product.ProductStatus.APPROVED,
        )
        .select_related('category', 'provider')
        .annotate(
            avg_rating=Avg('reviews__overall_rating'),
            review_count=Count('reviews'),
        )
        .prefetch_related(approved_images_prefetch)
    )


def log_event(request, obj, interaction_type, search_query=None):
    """
    Silently tracks user behavior for the recommendation engine only when
    analytics/personalization consent is granted (or for core cart/purchase events).
    """
    if interaction_type in ('VIEW', 'SEARCH') and not has_analytics_consent(request):
        return

    if not request.session.session_key:
        request.session.create()

    weights = {'VIEW': 1, 'SEARCH': 3, 'SAVE': 5, 'CART': 8, 'PURCHASE': 15}

    UserInteraction.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.id,
        interaction_type=interaction_type,
        weight=weights.get(interaction_type, 1),
        search_query=search_query,
    )


def get_smart_feed(request):
    """
    Hybrid Recommendation Engine.
    Returns non-personalized trending items if analytics cookies are not enabled
    or if the visitor has no browsing history yet.
    """
    base_qs = _get_approved_products_base_qs()

    if not has_analytics_consent(request):
        return {
            'is_personalized': False,
            'trending': list(base_qs.order_by('?')[:8]),
        }

    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key

    interactions = UserInteraction.objects.none()
    if user:
        interactions = UserInteraction.objects.filter(user=user)
    elif session_key:
        interactions = UserInteraction.objects.filter(session_key=session_key)

    product_ct = ContentType.objects.get_for_model(Product)
    product_history = interactions.filter(content_type=product_ct)

    # COLD START (New User with no history)
    if not product_history.exists():
        return {
            'is_personalized': False,
            'trending': list(base_qs.order_by('?')[:8]),
        }

    # SMART START (Returning User with Analytics Consent)
    interacted_ids = list(product_history.values_list('object_id', flat=True).distinct())

    top_category_ids = list(
        Product.objects.filter(id__in=interacted_ids)
        .values_list('category_id', flat=True)
        .distinct()
    )

    continue_viewing = list(base_qs.filter(id__in=interacted_ids)[:4])

    recommended = list(
        base_qs.filter(category_id__in=top_category_ids)
        .exclude(id__in=interacted_ids)
        .order_by('?')[:8]
    )

    return {
        'is_personalized': True,
        'continue_viewing': continue_viewing,
        'recommended': recommended,
        'trending': list(base_qs.order_by('?')[:4]),
    }