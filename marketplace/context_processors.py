from .models import Category
from orders.models import Cart

def global_categories(request):
    # This makes 'nav_categories' available in every single HTML template
    return {'nav_categories': Category.objects.filter(is_active=True)}

def cart_item_count(request):
    """
    Globally injects the user's total cart item count into all templates.
    """
    if request.user.is_authenticated:
        # Fetch the user's active cart
        cart = Cart.objects.filter(customer=request.user).first()
        if cart:
            # Count both physical products and booked services
            total = cart.items.count() + cart.jobs.count()
            return {'cart_count': total}
            
    # If not logged in, or cart is empty, return 0
    return {'cart_count': 0}