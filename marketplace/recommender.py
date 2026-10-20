from django.contrib.contenttypes.models import ContentType
from .models import UserInteraction, Product, Service

def log_event(request, obj, interaction_type, search_query=None):
    """Silently tracks user behavior for the recommendation engine."""
    # Ensure anonymous guests have a session key before logging
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
        search_query=search_query
    )

def get_smart_feed(request):
    """
    V1 Hybrid Recommendation Engine.
    Analyzes behavior to return personalized lists (Continue Viewing, Recommendations).
    """
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key

    # Fetch the user's history
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
            'trending': Product.objects.filter(is_active=True).order_by('?')[:8] # Randomized for V1 simulation
        }

    # SMART START (Returning User)
    interacted_ids = product_history.values_list('object_id', flat=True).distinct()
    
    # 1. Determine Category Affinity (What categories do they look at?)
    top_category_ids = Product.objects.filter(id__in=interacted_ids)\
        .values_list('category_id', flat=True).distinct()
        
    # 2. Build "Continue Viewing" (Items they looked at recently)
    continue_viewing = Product.objects.filter(id__in=interacted_ids, is_active=True)[:4]
    
    # 3. Build "Picked For You" (New items in their favorite categories)
    recommended = Product.objects.filter(category_id__in=top_category_ids, is_active=True)\
        .exclude(id__in=interacted_ids).order_by('?')[:8]
        
    return {
        'is_personalized': True,
        'continue_viewing': continue_viewing,
        'recommended': recommended,
        'trending': Product.objects.filter(is_active=True).order_by('?')[:4]
    }