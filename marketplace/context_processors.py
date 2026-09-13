from .models import Category

def global_categories(request):
    # This makes 'nav_categories' available in every single HTML template
    return {'nav_categories': Category.objects.filter(is_active=True)}