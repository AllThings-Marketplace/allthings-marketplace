from django.core.management.base import BaseCommand
from marketplace.models import Category

class Command(BaseCommand):
    help = 'Bulk updates existing categories with their dynamic JSON attribute schemas'

    def handle(self, *args, **kwargs):
        self.stdout.write("Injecting category attributes...")

        # Map the exact Category Name to its required JSON schema
        ATTRIBUTE_MAPPING = {
            # Computers & Tech
            "Laptops": [
                {"name": "RAM", "required": True},
                {"name": "Processor", "required": True},
                {"name": "Storage Capacity", "required": True},
                {"name": "Operating System", "required": False}
            ],
            "Desktops": [
                {"name": "RAM", "required": True},
                {"name": "Processor", "required": True},
                {"name": "Form Factor", "required": False}
            ],
            # Phones & Tablets
            "Smartphones": [
                {"name": "RAM", "required": True},
                {"name": "Internal Storage", "required": True},
                {"name": "Camera Megapixels", "required": False}
            ],
            "Power Banks": [
                {"name": "Battery Capacity (mAh)", "required": True},
                {"name": "Number of Ports", "required": True},
                {"name": "Fast Charging Supported", "required": False}
            ],
            # Electricals & Power
            "Generators": [
                {"name": "Power Output (kVA)", "required": True},
                {"name": "Starting System", "required": True},
                {"name": "Coil Material", "required": False}
            ],
            "Solar Panels": [
                {"name": "Wattage (W)", "required": True},
                {"name": "Cell Type (Monocrystalline/Polycrystalline)", "required": True}
            ],
            "Deep Cycle Batteries": [
                {"name": "Voltage (V)", "required": True},
                {"name": "Capacity (Ah)", "required": True},
                {"name": "Battery Chemistry (Tubular/Lithium/Gel)", "required": True}
            ],
            # Home Appliances
            "AC Units": [
                {"name": "Horsepower (HP)", "required": True},
                {"name": "Inverter Technology", "required": False}
            ],
            "Standing Fans": [
                {"name": "Blade Size (Inches)", "required": True},
                {"name": "Number of Speed Settings", "required": False}
            ],
            # Fashion & Apparel
            "Shirts": [
                {"name": "Material", "required": True},
                {"name": "Sleeve Length", "required": False}
            ],
            "Sneakers": [
                {"name": "Upper Material", "required": True},
                {"name": "Closure Type", "required": False}
            ]
        }

        updated_count = 0

        for category_name, schema in ATTRIBUTE_MAPPING.items():
            try:
                # Fetch the existing category
                category = Category.objects.get(name=category_name)
                # Overwrite the schema and save
                category.attribute_schema = schema
                category.save()
                updated_count += 1
                self.stdout.write(f"Updated: {category_name}")
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Skipped: '{category_name}' not found in database."))
            except Category.MultipleObjectsReturned:
                self.stdout.write(self.style.ERROR(f"Error: Multiple categories found with the name '{category_name}'."))

        self.stdout.write(self.style.SUCCESS(f'Successfully injected attributes into {updated_count} categories!'))