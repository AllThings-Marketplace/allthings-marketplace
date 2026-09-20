from .models import Category
from orders.models import Cart

def global_categories(request):
    # This makes 'nav_categories' available in every single HTML template
    return {'nav_categories': Category.objects.filter(is_active=True)}

def cart_item_count(request):
    """
    Globally injects the user's total cart item count into all templates.
    Now exclusively counts physical products.
    """
    if request.user.is_authenticated:
        cart = Cart.objects.filter(customer=request.user).first()
        if cart:
            return {'cart_count': cart.items.count()}
            
    return {'cart_count': 0}