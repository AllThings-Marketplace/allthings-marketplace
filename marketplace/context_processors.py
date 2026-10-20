from django.db.models import Sum
from .models import Category
from orders.models import Cart


def global_categories(request):
    # Makes 'nav_categories' available in every template with prefetched subcategories
    return {
        'nav_categories': Category.objects.filter(
            is_active=True
        ).prefetch_related('subcategories')
    }


def cart_item_count(request):
    """
    Globally injects the user's total cart unit quantity into all templates.
    Matches the Sum('quantity') logic used by the AJAX cart endpoints.
    """
    if request.user.is_authenticated:
        total_units = Cart.objects.filter(
            customer=request.user
        ).aggregate(total=Sum('items__quantity'))['total']
        return {'cart_count': total_units or 0}

    return {'cart_count': 0}