from django.core.management.base import BaseCommand
from marketplace.models import Category


class Command(BaseCommand):
    help = "Synchronizes dynamic JSON attribute schemas across all AllThings product and service categories."

    def handle(self, *args, **kwargs):
        self.stdout.write("Synchronizing AllThings category attribute schemas...")

        UNIVERSAL_PRODUCT_FALLBACK = [
            {"name": "Brand / Manufacturer", "required": False},
            {"name": "Condition (Brand New / Used / Refurbished)", "required": True},
            {"name": "Color / Variant", "required": False},
            {"name": "Warranty Period", "required": False},
        ]

        UNIVERSAL_SERVICE_FALLBACK = [
            {"name": "Service Mode (On-site / Shop / Remote)", "required": True},
            {"name": "Estimated Turnaround Time", "required": True},
            {"name": "Service Guarantee / Warranty", "required": False},
        ]

        # Inherit parent schema for any subcategory that currently has an empty schema
        inherited_count = 0
        subcategories_missing_schema = Category.objects.filter(
            parent__isnull=False,
            attribute_schema=[]
        ).select_related("parent")

        for sub in subcategories_missing_schema:
            if sub.parent and sub.parent.attribute_schema:
                sub.attribute_schema = sub.parent.attribute_schema
                sub.save(update_fields=["attribute_schema"])
                inherited_count += 1

        # Apply type-aware fallbacks to any remaining unmapped categories
        unmapped_products = Category.objects.filter(category_type="PRODUCT", attribute_schema=[])
        prod_fallback_count = unmapped_products.count()
        for cat in unmapped_products:
            cat.attribute_schema = UNIVERSAL_PRODUCT_FALLBACK
            cat.save(update_fields=["attribute_schema"])

        unmapped_services = Category.objects.filter(category_type="SERVICE", attribute_schema=[])
        srv_fallback_count = unmapped_services.count()
        for cat in unmapped_services:
            cat.attribute_schema = UNIVERSAL_SERVICE_FALLBACK
            cat.save(update_fields=["attribute_schema"])

        total_categories = Category.objects.filter(is_active=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Verified schemas across {total_categories} active categories "
                f"(Inherited: {inherited_count}, Product Fallbacks: {prod_fallback_count}, Service Fallbacks: {srv_fallback_count})."
            )
        )