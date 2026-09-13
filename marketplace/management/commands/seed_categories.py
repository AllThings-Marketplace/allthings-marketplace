from django.core.management.base import BaseCommand
from django.utils.text import slugify
from marketplace.models import Category

class Command(BaseCommand):
    help = 'Bulk seeds the marketplace category taxonomy'

    def generate_unique_slug(self, name):
        """Generates a unique slug by appending a number if a collision occurs."""
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding categories...")

        # The Master Category Dictionary
        CATEGORY_TREE = {
            "Computers & Tech": {
                "Laptops": ["Gaming Laptops", "Business Laptops", "MacBooks"],
                "Desktops": ["All-in-One PCs", "Tower Workstations", "Mini PCs"],
                "Networking": ["Routers", "Switches", "WiFi Extenders"],
                "Storage": ["External HDDs", "SSDs", "Flash Drives"],
            },
            "Phones & Tablets": {
                "Smartphones": ["Android Phones", "iOS Devices", "Refurbished Phones"],
                "Tablets": ["iPads", "Android Tablets", "E-Readers"],
                "Accessories": ["Power Banks", "Screen Guards", "Chargers & Cables"],
            },
            "Electricals & Power": {
                "Generators": ["Petrol Generators", "Diesel Generators", "Inverter Generators"],
                "Solar Systems": ["Solar Panels", "Deep Cycle Batteries", "Solar Inverters"],
                "Wiring & Cables": ["Extension Boards", "Circuit Breakers", "Copper Cables"],
            },
            "Home Appliances": {
                "Kitchen": ["Blenders", "Microwaves", "Air Fryers"],
                "Laundry": ["Washing Machines", "Dryers", "Irons"],
                "Climate Control": ["AC Units", "Standing Fans", "Heaters"],
            },
            "Automotive & Riding": {
                "Motorcycles & Gear": ["Riding Helmets", "Protective Jackets", "Riding Gloves", "Motorcycle Parts"],
                "Car Accessories": ["Dash Cams", "Car Care Products", "Floor Mats"],
                "Tools": ["Jack Stands", "Wrench Sets", "Tire Inflators"],
            },
            "Fashion & Apparel": {
                "Men's Wear": ["Shirts", "Trousers", "Traditional Attire"],
                "Women's Wear": ["Dresses", "Tops", "Skirts"],
                "Footwear": ["Sneakers", "Formal Shoes", "Sandals"],
                "Accessories": ["Wristwatches", "Sunglasses", "Belts"],
            },
            "Health & Beauty": {
                "Skincare": ["Face Serums", "Lotions", "Sunscreen"],
                "Haircare": ["Wigs", "Shampoos", "Clippers"],
                "Fragrances": ["Designer Perfumes", "Body Mists", "Oud Oils"],
            },
            "Professional Services": {
                "Installations": ["Solar Setup", "AC Installation", "CCTV Installation"],
                "Repairs": ["Phone Repair", "Laptop Repair", "Plumbing"],
                "Consulting & Digital": ["Web Design", "Graphic Design", "IT Support"],
            }
        }

        created_count = 0

        # Loop through the dictionary and create the tree
        for main_cat_name, sub_cats in CATEGORY_TREE.items():
            # Create Parent Category
            parent_cat, created = Category.objects.get_or_create(
                name=main_cat_name,
                parent=None,
                defaults={
                    'is_active': True,
                    'slug': self.generate_unique_slug(main_cat_name)
                }
            )
            if created:
                created_count += 1

            for sub_cat_name, niches in sub_cats.items():
                # Create Subcategory
                sub_cat, created = Category.objects.get_or_create(
                    name=sub_cat_name,
                    parent=parent_cat,
                    defaults={
                        'is_active': True,
                        'slug': self.generate_unique_slug(sub_cat_name)
                    }
                )
                if created:
                    created_count += 1

                for niche_name in niches:
                    # Create Niche Branch
                    niche_cat, created = Category.objects.get_or_create(
                        name=niche_name,
                        parent=sub_cat,
                        defaults={
                            'is_active': True,
                            'slug': self.generate_unique_slug(niche_name)
                        }
                    )
                    if created:
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} categories!'))