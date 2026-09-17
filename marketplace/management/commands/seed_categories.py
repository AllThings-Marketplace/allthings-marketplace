from django.core.management.base import BaseCommand
from django.utils.text import slugify
from marketplace.models import Category

class Command(BaseCommand):
    help = 'Bulk seeds a universal marketplace category taxonomy'

    def generate_unique_slug(self, name):
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding universal categories...")

        CATEGORY_TREE = {
            # --- TECHNOLOGY & ELECTRONICS ---
            "Computers & Tech": {
                "Laptops": ["Gaming Laptops", "Business Laptops", "MacBooks", "Chromebooks"],
                "Desktops": ["All-in-One PCs", "Tower Workstations", "Mini PCs"],
                "Networking": ["Routers", "Switches", "WiFi Extenders", "Server Racks"],
                "Storage": ["External HDDs", "SSDs", "Flash Drives", "NAS Systems"],
                "Peripherals": ["Monitors", "Keyboards & Mice", "Printers", "Webcams"],
            },
            "Phones & Tablets": {
                "Smartphones": ["Android Phones", "iOS Devices", "Refurbished Phones"],
                "Tablets": ["iPads", "Android Tablets", "E-Readers"],
                "Accessories": ["Power Banks", "Screen Guards", "Chargers & Cables", "Cases"],
                "Wearables": ["Smartwatches", "Fitness Trackers", "VR Headsets"],
            },
            "Audio & Video": {
                "Headphones": ["Wireless Earbuds", "Over-Ear Headphones", "Studio Monitors"],
                "Speakers": ["Bluetooth Speakers", "Home Theater", "Soundbars"],
                "Cameras": ["DSLRs", "Mirrorless", "CCTV & Security", "Drones"],
            },

            # --- ELECTRICAL, POWER & HARDWARE ---
            "Electricals & Power": {
                "Generators": ["Petrol Generators", "Diesel Generators", "Inverter Generators"],
                "Solar Systems": ["Solar Panels", "Deep Cycle Batteries", "Solar Inverters", "Charge Controllers"],
                "Wiring & Cables": ["Extension Boards", "Circuit Breakers", "Copper Cables", "Switches & Sockets"],
                "Lighting": ["LED Bulbs", "Floodlights", "Chandeliers", "Street Lights"],
            },
            "Industrial & Tools": {
                "Power Tools": ["Drills", "Grinders", "Saws"],
                "Hand Tools": ["Wrench Sets", "Screwdrivers", "Hammers"],
                "Safety Equipment": ["Helmets", "Work Boots", "Reflective Gear", "Fire Extinguishers"],
            },

            # --- HOME, LIFESTYLE & FASHION ---
            "Home & Office": {
                "Kitchen Appliances": ["Blenders", "Microwaves", "Air Fryers", "Refrigerators"],
                "Laundry & Cleaning": ["Washing Machines", "Vacuum Cleaners", "Irons"],
                "Climate Control": ["AC Units", "Standing Fans", "Heaters", "Air Purifiers"],
                "Furniture": ["Office Chairs", "Desks", "Sofas", "Beds"],
            },
            "Fashion & Apparel": {
                "Men's Wear": ["Shirts", "Trousers", "Traditional Attire", "Suits"],
                "Women's Wear": ["Dresses", "Tops", "Skirts", "Activewear"],
                "Footwear": ["Sneakers", "Formal Shoes", "Sandals", "Boots"],
                "Accessories": ["Wristwatches", "Sunglasses", "Belts", "Jewelry"],
                "Bags & Luggage": ["Backpacks", "Handbags", "Suitcases"],
            },
            "Health & Beauty": {
                "Skincare & Hair": ["Face Serums", "Lotions", "Shampoos", "Wigs"],
                "Makeup & Fragrances": ["Perfumes", "Foundations", "Oud Oils"],
                "Wellness & Fitness": ["Vitamins", "Yoga Mats", "Dumbbells", "Treadmills"],
            },

            # --- VEHICLES & TRANSPORT ---
            "Automotive & Riding": {
                "Motorcycles & Gear": ["Riding Helmets", "Protective Jackets", "Motorcycle Parts"],
                "Car Accessories": ["Dash Cams", "Car Care Products", "Floor Mats", "Stereo Systems"],
                "Auto Parts": ["Batteries", "Tires", "Brake Pads", "Engine Oil"],
            },

            # --- MISCELLANEOUS GOODS ---
            "Books, Media & Gaming": {
                "Gaming": ["Consoles", "Video Games", "Gaming Controllers"],
                "Books": ["Educational", "Fiction", "Business & Finance"],
                "Musical Instruments": ["Guitars", "Keyboards", "Studio Equipment"],
            },
            "Groceries & Consumables": {
                "Packaged Food": ["Rice & Pasta", "Canned Goods", "Snacks"],
                "Beverages": ["Water", "Juices", "Alcoholic Drinks"],
                "Household Supplies": ["Detergents", "Paper Towels", "Cleaning Liquids"],
            },

            # --- COMPREHENSIVE SERVICES ---
            "Professional Services": {
                "Installations": ["Solar Setup", "AC Installation", "CCTV Installation", "DSTV Setup"],
                "Repairs & Maintenance": ["Phone Repair", "Laptop Repair", "Plumbing", "Auto Mechanic"],
                "Digital & Creative": ["Web Development", "Graphic Design", "Video Editing", "Digital Marketing"],
                "Consulting & Business": ["Legal Services", "Accounting", "Business Registration", "Tax Consulting"],
                "Home Services": ["House Cleaning", "Pest Control", "Moving & Relocation", "Landscaping"],
                "Personal Services": ["Photography", "Event Planning", "Tailoring", "Tutoring"],
            }
        }

        created_count = 0

        for main_cat_name, sub_cats in CATEGORY_TREE.items():
            parent_cat, created = Category.objects.get_or_create(
                name=main_cat_name, parent=None,
                defaults={'is_active': True, 'slug': self.generate_unique_slug(main_cat_name)}
            )
            if created: created_count += 1

            for sub_cat_name, niches in sub_cats.items():
                sub_cat, created = Category.objects.get_or_create(
                    name=sub_cat_name, parent=parent_cat,
                    defaults={'is_active': True, 'slug': self.generate_unique_slug(sub_cat_name)}
                )
                if created: created_count += 1

                for niche_name in niches:
                    niche_cat, created = Category.objects.get_or_create(
                        name=niche_name, parent=sub_cat,
                        defaults={'is_active': True, 'slug': self.generate_unique_slug(niche_name)}
                    )
                    if created: created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} universal categories!'))