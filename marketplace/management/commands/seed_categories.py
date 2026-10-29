from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from marketplace.models import Category, Product, Service


# Reusable Base Schemas
TECH_SCHEMA = [
    {"name": "Brand", "required": True},
    {"name": "Model", "required": True},
    {"name": "Condition (Brand New / UK Used / Refurbished)", "required": True},
    {"name": "Warranty Period", "required": False},
]

FASHION_SCHEMA = [
    {"name": "Brand / Designer", "required": False},
    {"name": "Available Sizes", "required": True},
    {"name": "Color", "required": True},
    {"name": "Material / Fabric", "required": False},
    {"name": "Gender (Men / Women / Unisex)", "required": True},
]

BEAUTY_SCHEMA = [
    {"name": "Brand", "required": True},
    {"name": "Size / Volume / Weight", "required": False},
    {"name": "Skin / Hair Type", "required": False},
]

APPLIANCE_SCHEMA = [
    {"name": "Brand", "required": True},
    {"name": "Power / Capacity Rating", "required": True},
    {"name": "Condition (New / Foreign Used)", "required": True},
    {"name": "Warranty Period", "required": False},
]

AUTO_SCHEMA = [
    {"name": "Make / Brand", "required": True},
    {"name": "Model & Year", "required": True},
    {"name": "Condition (Brand New / Foreign Used / Nigerian Used)", "required": True},
]

DEFAULT_SERVICE_SCHEMA = [
    {"name": "Service Mode (Home Visit / Shop / Remote)", "required": True},
    {"name": "Estimated Turnaround Time", "required": True},
    {"name": "Service Warranty / Guarantee", "required": False},
]


PRODUCT_CATEGORIES = [
    # ------------------------------------------------------------------
    # 1. PHONES, TABLETS & ACCESSORIES
    # ------------------------------------------------------------------
    {
        "name": "Phones, Tablets & Wearables",
        "keywords": "phone, smartphone, iphone, samsung, tecno, infinix, xiaomi, redmi, itel, ipad, tablet, smartwatch, airpods, earpods, powerbank, charger",
        "schema": TECH_SCHEMA,
        "subcategories": [
            {
                "name": "Smartphones (Android & iPhones)",
                "keywords": "iphone, samsung galaxy, tecno, infinix, xiaomi, redmi, pixel, oppo, vivo, itel, 5g phone, android phone, ios",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Storage Capacity (e.g., 128GB, 256GB)", "required": True},
                    {"name": "RAM Size (e.g., 8GB, 12GB)", "required": True},
                    {"name": "Condition (Brand New / UK Used)", "required": True},
                    {"name": "Color", "required": False},
                ],
            },
            {
                "name": "Tablets, iPads & E-Readers",
                "keywords": "ipad, samsung tab, tablet, kids tablet, kindle, stylus tablet, android tablet",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Screen Size (Inches)", "required": True},
                    {"name": "Storage & Connectivity (Wi-Fi / Cellular)", "required": True},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Smartwatches & Fitness Trackers",
                "keywords": "apple watch, galaxy watch, smartwatch, fitness band, ultra watch, oraimo watch, xiaomi band",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Case Size / Strap Type", "required": False},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Phone Accessories, Power Banks & Chargers",
                "keywords": "power bank, powerbank, fast charger, type c cable, lightning cable, airpods, earbuds, phone case, screen guard, ring light, tripod, oraimo, anker, new age",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Compatibility / Port Type", "required": True},
                    {"name": "Capacity / Wattage (mAh or W)", "required": False},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 2. COMPUTING, LAPTOPS & NETWORKING
    # ------------------------------------------------------------------
    {
        "name": "Computing, Laptops & Office Tech",
        "keywords": "laptop, macbook, hp, dell, lenovo, thinkpad, vaio, asus, acer, monitor, desktop, ssd, ram, router, mifi, starlink, printer, keyboard, mouse",
        "schema": TECH_SCHEMA,
        "subcategories": [
            {
                "name": "Laptops, MacBooks & Ultrabooks",
                "keywords": "laptop, macbook pro, macbook air, hp elitebook, hp pavilion, dell xps, dell latitude, lenovo thinkpad, sony vaio, gaming laptop, core i5, core i7, ryzen",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Processor (e.g., Core i5, Core i7, M2)", "required": True},
                    {"name": "RAM Size (e.g., 8GB, 16GB, 32GB)", "required": True},
                    {"name": "Storage Size & Type (e.g., 512GB SSD)", "required": True},
                    {"name": "Screen Size (Inches)", "required": False},
                    {"name": "Condition (Brand New / UK Used)", "required": True},
                ],
            },
            {
                "name": "Desktops, All-in-Ones & Monitors",
                "keywords": "desktop pc, monitor, gaming monitor, 144hz, 4k monitor, all in one pc, imac, workstation, cpu",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Screen Size / Resolution", "required": True},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Storage, RAM, Keyboards & Peripherals",
                "keywords": "ssd, nvme, external hard drive, flash drive, ram, mechanical keyboard, wireless mouse, webcam, usb hub, laptop charger, laptop battery",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Capacity / Specification", "required": True},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Wi-Fi Routers, MiFi & Starlink Kits",
                "keywords": "mifi, 4g router, 5g router, starlink, mtn mifi, airtel router, tp-link, network switch, ethernet cable, wifi extender",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Network Standard (4G / 5G / Wi-Fi 6 / Satellite)", "required": True},
                    {"name": "Unlocked Status", "required": False},
                ],
            },
            {
                "name": "Printers, Scanners & POS Hardware",
                "keywords": "printer, laserjet, ink tank, epson, canonprinter, hp printer, scanner, pos machine, thermal printer, toner",
                "schema": TECH_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 3. ELECTRONICS, TV, GAMING & AUDIO
    # ------------------------------------------------------------------
    {
        "name": "Electronics, TV, Audio & Gaming",
        "keywords": "tv, smart tv, television, lg, hisense, samsung tv, soundbar, home theatre, speaker, jbl, ps5, ps4, playstation, xbox, controller, camera, drone",
        "schema": TECH_SCHEMA,
        "subcategories": [
            {
                "name": "Smart TVs, LED & QLED Televisions",
                "keywords": "smart tv, 4k tv, oled, qled, led tv, 32 inch, 43 inch, 50 inch, 55 inch, 65 inch, 75 inch, lg, samsung, hisense, tcl, nexus",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Screen Size (Inches)", "required": True},
                    {"name": "Display Resolution (FHD / 4K UHD / QLED)", "required": True},
                    {"name": "Smart OS (WebOS / Google TV / Tizen)", "required": False},
                ],
            },
            {
                "name": "Home Theatres, Soundbars & Bluetooth Speakers",
                "keywords": "soundbar, home theatre, bluetooth speaker, subwoofer, jbl, sony audio, lg xboom, zeolot, studio monitor, microphone",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Power Output (Watts)", "required": False},
                    {"name": "Connectivity (Bluetooth / HDMI ARC / AUX)", "required": True},
                ],
            },
            {
                "name": "PlayStation, Xbox, Consoles & Gaming Gear",
                "keywords": "ps5, ps4, playstation, xbox, nintendo switch, dualshock, dualsense, game pad, gaming controller, fifa, fc25, gta, gaming headset",
                "schema": [
                    {"name": "Platform (PS5 / PS4 / Xbox / PC / Switch)", "required": True},
                    {"name": "Condition (Brand New / Used)", "required": True},
                    {"name": "Storage / Edition", "required": False},
                ],
            },
            {
                "name": "Cameras, Drones, Gimbals & Studio Lighting",
                "keywords": "camera, dslr, mirrorless, canon, sony alpha, nikon, dji drone, osmo, gimbal, softbox, studio light, Action camera, gopro",
                "schema": TECH_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 4. HOME, KITCHEN & MAJOR APPLIANCES
    # ------------------------------------------------------------------
    {
        "name": "Home, Kitchen & Major Appliances",
        "keywords": "fridge, freezer, air conditioner, ac, fan, washing machine, blender, microwave, air fryer, gas cooker, furniture, mattress, cookware",
        "schema": APPLIANCE_SCHEMA,
        "subcategories": [
            {
                "name": "Refrigerators, Chest Freezers & Dispensers",
                "keywords": "fridge, refrigerator, double door fridge, chest freezer, deep freezer, water dispenser, hisense, haier thermocool, lg, bruhm",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Capacity (Litres)", "required": True},
                    {"name": "Type (Single Door / Double Door / Chest Freezer)", "required": True},
                    {"name": "Energy Saving / Inverter Compressor", "required": False},
                ],
            },
            {
                "name": "Air Conditioners, Rechargeable Fans & Coolers",
                "keywords": "air conditioner, split ac, standing ac, 1hp, 1.5hp, 2hp, inverter ac, rechargeable fan, standing fan, ox fan, binatone, lontor, hisense ac",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Capacity / Size (e.g., 1HP, 1.5HP, 18-Inch)", "required": True},
                    {"name": "Type (Inverter AC / Non-Inverter / Rechargeable Fan)", "required": True},
                ],
            },
            {
                "name": "Washing Machines & Garment Care",
                "keywords": "washing machine, front load, top load, twin tub, clothes dryer, pressing iron, steam iron",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Wash Capacity (kg)", "required": True},
                    {"name": "Loader Type (Front Load / Top Load / Twin Tub)", "required": True},
                ],
            },
            {
                "name": "Kitchen Appliances (Cookers, Blenders & Air Fryers)",
                "keywords": "gas cooker, table burner, microwave, oven, air fryer, blender, silver crest, food processor, electric kettle, toaster, buchymix",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Wattage / Burners / Capacity", "required": True},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Furniture, Mattresses, Bedding & Home Decor",
                "keywords": "sofa, chair, office chair, desk, dining table, bed frame, mattress, mouka foam, duvet, curtains, rug, wall art, throw pillow, pots, cookware",
                "schema": [
                    {"name": "Material / Finish", "required": True},
                    {"name": "Dimensions / Size (e.g., 6x6ft, Ergonomic)", "required": True},
                    {"name": "Color", "required": False},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 5. SOLAR, INVERTERS & POWER BACKUP
    # ------------------------------------------------------------------
    {
        "name": "Solar, Inverters & Power Backup",
        "keywords": "solar, inverter, battery, lithium, lifepo4, tubular, mppt, charge controller, panel, power station, power tank, generator, kva, felicity, deye, luminous, itel",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Warranty Period", "required": False},
        ],
        "subcategories": [
            {
                "name": "Hybrid & Pure Sine Wave Inverters",
                "keywords": "inverter, hybrid inverter, pure sine wave, kva, kw, 1.5kva, 3kva, 5kva, 8kva, 10kva, 12v, 24v, 48v, felicity, deye, growatt, luminous, kartel",
                "schema": [
                    {"name": "Rated Capacity (kVA / kW)", "required": True},
                    {"name": "System Battery Voltage (12V/24V/48V)", "required": True},
                    {"name": "Inverter Type (Hybrid / Non-Hybrid)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Solar Panels (Monocrystalline & Bifacial)",
                "keywords": "solar panel, monocrystalline, polycrystalline, bifacial, half cut, jinko, canadian solar, longi, trina, 200w, 300w, 450w, 550w, 600w",
                "schema": [
                    {"name": "Rated Power (Watts)", "required": True},
                    {"name": "Cell Type (Mono / Bifacial)", "required": True},
                    {"name": "Open Circuit Voltage (Voc)", "required": False},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Lithium (LiFePO4) & Tubular Batteries",
                "keywords": "battery, lithium battery, lifepo4, tubular battery, deep cycle, agm, gel, 200ah, 220ah, 5kwh, 10kwh, 15kwh, felicity, luminous, starplus, eastman",
                "schema": [
                    {"name": "Capacity (Ah or kWh)", "required": True},
                    {"name": "Nominal Voltage (12V / 24V / 48V)", "required": True},
                    {"name": "Battery Chemistry (LiFePO4 / Tubular / Gel)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "MPPT & PWM Solar Charge Controllers",
                "keywords": "charge controller, mppt, pwm, 40a, 60a, 80a, 100a, fangpusun, felicity, powmr",
                "schema": [
                    {"name": "Max Current Rating (Amps)", "required": True},
                    {"name": "System Voltage (12V/24V/48V Auto)", "required": True},
                    {"name": "Controller Type (MPPT / PWM)", "required": True},
                ],
            },
            {
                "name": "Portable Power Stations & Generators",
                "keywords": "power station, power tank, solar generator, itel power tank, ecoflow, bluetti, firman generator, lutian, thermocool generator, inverter generator",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Capacity (Wh / kVA)", "required": True},
                    {"name": "Power Source (Solar Battery / Petrol / Diesel)", "required": True},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 6. ELECTRICALS, WIRING, LIGHTING & TOOLS
    # ------------------------------------------------------------------
    {
        "name": "Electricals, Lighting & Hardware Tools",
        "keywords": "wire, cable, conduit, breaker, db, mcb, changeover, avr, stabilizer, switch, socket, led bulb, chandelier, floodlight, multimeter, drill, tool",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Specification / Rating", "required": True},
        ],
        "subcategories": [
            {
                "name": "House Wiring & Building Cables",
                "keywords": "single core, twin and earth, flat cable, 1.5mm, 2.5mm, 4mm, 6mm, 10mm, 16mm, coil, copper wire, pvc wire, coleman, cutix, nigerchin",
                "schema": [
                    {"name": "Cable Gauge (mm²)", "required": True},
                    {"name": "Core Type (Single / Twin & Earth)", "required": True},
                    {"name": "Coil Length (m)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Armoured & Underground Cables",
                "keywords": "armoured, swa, underground, 25mm, 35mm, 50mm, 70mm, 95mm, 4 core, 3 core, high tension, feeder pillar cable",
                "schema": [
                    {"name": "Cable Size (mm²)", "required": True},
                    {"name": "Number of Cores", "required": True},
                    {"name": "Conductor (Copper / Aluminium)", "required": True},
                    {"name": "Brand", "required": False},
                ],
            },
            {
                "name": "Flexible Cords & Control Cables",
                "keywords": "flexible cable, flex, 3 core flex, appliance cord, extension wire, submersible cable, welding cable",
                "schema": [
                    {"name": "Core Count & Gauge", "required": True},
                    {"name": "Roll Length (m)", "required": True},
                    {"name": "Brand", "required": False},
                ],
            },
            {
                "name": "PVC Conduits, Trunking & Accessories",
                "keywords": "conduit pipe, pvc pipe, trunking, adaptable box, circular box, coupler, saddle clip, bend, 20mm, 25mm, patress box",
                "schema": [
                    {"name": "Size / Diameter (mm)", "required": True},
                    {"name": "Material (PVC / Galvanized)", "required": True},
                    {"name": "Pack Quantity", "required": False},
                ],
            },
            {
                "name": "Distribution Boards (DB) & Consumer Units",
                "keywords": "distribution board, db box, consumer unit, 4 way, 6 way, 8 way, 12 way, 16 way, single phase db, three phase tpn",
                "schema": [
                    {"name": "Number of Ways", "required": True},
                    {"name": "Phase Type (Single Phase / 3-Phase TPN)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Circuit Breakers (MCB, MCCB, RCD & ELCB)",
                "keywords": "mcb, mccb, rcd, elcb, circuit breaker, miniature breaker, 16a, 20a, 32a, 63a, 100a, 1p, 2p, 3p, 4p, schneider, abb, havells",
                "schema": [
                    {"name": "Amperage Rating (A)", "required": True},
                    {"name": "Number of Poles (1P / 2P / 3P / 4P)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Changeover Switches, ATS & Isolators",
                "keywords": "changeover, automatic transfer switch, ats, isolator, 63a, 100a, 200a, 400a, socomec",
                "schema": [
                    {"name": "Current Rating (Amps)", "required": True},
                    {"name": "Operation Mode (Manual / Automatic ATS)", "required": True},
                ],
            },
            {
                "name": "Voltage Stabilizers (AVR) & Surge Protectors",
                "keywords": "stabilizer, avr, voltage regulator, surge protector, tv guard, fridge guard, 5000va, 10kva, binatone, sollatek",
                "schema": [
                    {"name": "Capacity (VA / kVA)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Wall Switches & Dimmers",
                "keywords": "wall switch, 1 gang, 2 gang, 3 gang, 4 gang, 1 way, 2 way, dimmer",
                "schema": [
                    {"name": "Gang Count (1G / 2G / 3G / 4G)", "required": True},
                    {"name": "Switch Type (1-Way / 2-Way)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Wall Sockets & Power Outlets",
                "keywords": "wall socket, 13a socket, double socket, single socket, usb socket, water heater switch, extension box",
                "schema": [
                    {"name": "Amperage Rating (13A / 15A / 45A)", "required": True},
                    {"name": "Gang Configuration", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "LED Bulbs, Tubes & POP Downlights",
                "keywords": "led bulb, energy bulb, pop light, panel light, downlight, chandelier, t8 tube, 9w, 12w, 18w, akt, vellmax",
                "schema": [
                    {"name": "Wattage (Watts)", "required": True},
                    {"name": "Fitting Type (E27 / B22 / Recessed)", "required": True},
                    {"name": "Brand", "required": False},
                ],
            },
            {
                "name": "Floodlights & Solar Security Lights",
                "keywords": "floodlight, solar street light, security light, 50w, 100w, 200w, ip65",
                "schema": [
                    {"name": "Power Rating (Watts)", "required": True},
                    {"name": "Weatherproof Rating (IP65 / IP66)", "required": False},
                ],
            },
            {
                "name": "Multimeters & Clamp Meters",
                "keywords": "multimeter, digital multimeter, clamp meter, voltage detector, uni-t, fluke",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Measurement Functions", "required": False},
                ],
            },
            {
                "name": "Electrician Hand & Power Tools",
                "keywords": "drill, cordless drill, angle grinder, crimping tool, cable cutter, wire stripper, pliers, screwdriver set, tool box, ingco, total, bosch",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Power Source (Cordless / Corded / Manual)", "required": False},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 7. FASHION, CLOTHING, FOOTWEAR & ACCESSORIES
    # ------------------------------------------------------------------
    {
        "name": "Fashion, Clothing, Shoes & Jewelry",
        "keywords": "shirt, dress, trousers, jeans, native wear, senator, agbada, gown, sneakers, shoes, heels, slides, handbag, watch, jewelry, sunglasses",
        "schema": FASHION_SCHEMA,
        "subcategories": [
            {
                "name": "Men's Clothing, Streetwear & Native Wear",
                "keywords": "men shirt, polo, t-shirt, jeans, chinos, hoodie, tracksuit, senator wear, kaftan, agbada, suit, blazer, boxers",
                "schema": FASHION_SCHEMA,
            },
            {
                "name": "Women's Dresses, Two-Piece & Corporate Wear",
                "keywords": "gown, dress, two piece, jumpsuit, blouse, skirt, abaya, ankara, kimono, activewear, lingerie, swimwear",
                "schema": FASHION_SCHEMA,
            },
            {
                "name": "Sneakers, Shoes, Heels, Loafers & Slides",
                "keywords": "sneakers, nike, adidas, jordan, timberland, loafers, corporate shoes, heels, sandals, slides, crocs, slippers, boots",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "EU / UK Shoe Size", "required": True},
                    {"name": "Color", "required": True},
                    {"name": "Gender (Men / Women / Unisex)", "required": True},
                ],
            },
            {
                "name": "Handbags, Backpacks, Wallets & Luggage",
                "keywords": "handbag, tote bag, crossbody bag, laptop backpack, travel box, suitcase, wallet, purse, belt",
                "schema": [
                    {"name": "Brand", "required": False},
                    {"name": "Material (Leather / Canvas / Hard-Shell)", "required": True},
                    {"name": "Color", "required": True},
                ],
            },
            {
                "name": "Watches, Jewelry, Sunglasses & Accessories",
                "keywords": "wristwatch, casio, chronograph, necklace, chain, bracelet, earrings, wedding ring, sunglasses, glasses, cap, hat",
                "schema": [
                    {"name": "Brand", "required": False},
                    {"name": "Material (Gold Plated / Silver / Stainless Steel)", "required": True},
                    {"name": "Gender", "required": False},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 8. HEALTH, BEAUTY, HAIR & PERSONAL CARE
    # ------------------------------------------------------------------
    {
        "name": "Health, Beauty, Hair & Personal Care",
        "keywords": "wig, human hair, bone straight, braids, attachment, skincare, lotion, serum, cream, perfume, fragrance, makeup, clipper, supplements",
        "schema": BEAUTY_SCHEMA,
        "subcategories": [
            {
                "name": "Wigs, Human Hair Bundles & Extensions",
                "keywords": "bone straight, human hair wig, closure, frontal, pixie curl, bob wig, braiding hair, expression attachment, wig cap, hair glue, edge control",
                "schema": [
                    {"name": "Hair Type (100% Human Hair / Blend / Synthetic)", "required": True},
                    {"name": "Length (Inches)", "required": True},
                    {"name": "Lace Type (Closure / Frontal / Glueless)", "required": True},
                    {"name": "Color / Texture", "required": False},
                ],
            },
            {
                "name": "Skincare, Body Lotions, Serums & Soaps",
                "keywords": "skincare, face serum, vitamin c, sunscreen, body lotion, cleanser, toner, exfoliating scrub, black soap, cerave, nivea, cetaphil",
                "schema": BEAUTY_SCHEMA,
            },
            {
                "name": "Perfumes, Oud, Body Mists & Deodorants",
                "keywords": "perfume, eau de parfum, oud, lattafa, dior, sauvage, body splash, Victoria secret, roll on, deodorant, cologne",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Volume (ml)", "required": True},
                    {"name": "Scent Type (EDP / EDT / Body Mist / Oil)", "required": True},
                ],
            },
            {
                "name": "Makeup, Nail Tech Supplies & Grooming Clippers",
                "keywords": "foundation, lipstick, lip gloss, eyeshadow, powder, makeup brush, acrylic powder, uv nail lamp, gel polish, wahl clipper, hair dryer, straightener",
                "schema": BEAUTY_SCHEMA,
            },
            {
                "name": "Health, Wellness, Vitamins & Medical Gear",
                "keywords": "vitamin, supplement, protein powder, blood pressure monitor, glucometer, first aid kit, posture corrector, massage gun",
                "schema": BEAUTY_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 9. AUTOMOBILES, MOTORCYCLES & SPARE PARTS
    # ------------------------------------------------------------------
    {
        "name": "Automobiles, Motorcycles & Spare Parts",
        "keywords": "car, toyota, honda, mercedes, lexus, motorcycle, power bike, bike, helmet, tyre, car battery, engine oil, brake pad, dashcam",
        "schema": AUTO_SCHEMA,
        "subcategories": [
            {
                "name": "Cars, SUVs & Commercial Vehicles",
                "keywords": "toyota, camry, corolla, rav4, highlander, lexus rx, honda accord, mercedes benz, ford, bus, Hilux, tokunbo car, nigerian used car",
                "schema": [
                    {"name": "Make & Model", "required": True},
                    {"name": "Year of Manufacture", "required": True},
                    {"name": "Condition (Foreign Used / Nigerian Used / Brand New)", "required": True},
                    {"name": "Transmission (Automatic / Manual)", "required": True},
                ],
            },
            {
                "name": "Motorcycles, Power Bikes, Scooters & Tricycles",
                "keywords": "motorcycle, power bike, sportbike, yamaha, honda bike, suzuki, kawasaki, bajaj, tvs, dispatch bike, scooter, keke, tricycle",
                "schema": [
                    {"name": "Make & Model", "required": True},
                    {"name": "Engine Capacity (cc)", "required": True},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Motorcycle Helmets, Riding Jackets & Bike Gear",
                "keywords": "helmet, full face helmet, riding gloves, riding jacket, knee guards, bike exhaust, motorcycle tyre, chain lube, bluetooth intercom",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Size (S / M / L / XL)", "required": True},
                    {"name": "Condition", "required": True},
                ],
            },
            {
                "name": "Auto Spare Parts, Tyres, Oils & Car Accessories",
                "keywords": "car tyre, car battery, engine oil, mobil, castrol, brake pad, shock absorber, headlamp, car stereo, reverse camera, dashcam, car inflator",
                "schema": [
                    {"name": "Brand / Manufacturer", "required": True},
                    {"name": "Compatible Vehicle / Specification", "required": True},
                    {"name": "Condition (New OEM / Tokunbo)", "required": True},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 10. BUILDING MATERIALS, PLUMBING & SECURITY HARDWARE
    # ------------------------------------------------------------------
    {
        "name": "Building Materials, Plumbing & Hardware",
        "keywords": "plumbing, water heater, water tank, tap, wc, sink, paint, tiles, security door, smart lock, cctv, safety boot, helmet",
        "schema": [
            {"name": "Brand", "required": False},
            {"name": "Material / Specification", "required": True},
        ],
        "subcategories": [
            {
                "name": "Plumbing Pipes, Water Heaters, Pumps & Sanitary Ware",
                "keywords": "water heater, ariston, pumping machine, submersible pump, water closet, wc, wash hand basin, kitchen sink, shower mixer, pvc pipe, geepee tank",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Capacity / Size", "required": True},
                ],
            },
            {
                "name": "Doors, Smart Locks, Paints & Finishing Materials",
                "keywords": "security door, turkey door, smart door lock, fingerprint lock, padlock, emulsion paint, satin paint, wall tiles, floor tiles, pop cement",
                "schema": [
                    {"name": "Brand", "required": False},
                    {"name": "Dimensions / Volume", "required": True},
                ],
            },
            {
                "name": "CCTV Cameras, Fire Alarms & Safety PPE",
                "keywords": "cctv camera, solar cctv, hikvision, dahua, fire extinguisher, smoke detector, safety boots, reflective jacket, hard hat",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Specification / Rating", "required": True},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 11. SUPERMARKET, GROCERIES & HOUSEHOLD SUPPLIES
    # ------------------------------------------------------------------
    {
        "name": "Supermarket, Groceries & Beverages",
        "keywords": "rice, oil, pasta, noodles, indomie, provisions, milk, milo, cereal, wine, juice, water, detergent, tissue, disinfectant",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Weight / Pack Size", "required": True},
            {"name": "Expiry Date", "required": False},
        ],
        "subcategories": [
            {
                "name": "Rice, Grains, Cooking Oil & Pantry Staples",
                "keywords": "bag of rice, basmati, vegetable oil, groundnut oil, palm oil, spaghetti, indomie, noodles, garri, beans, semovita, seasoning, tomato paste",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Weight / Volume (e.g., 5kg, 25kg, 5L)", "required": True},
                ],
            },
            {
                "name": "Breakfast, Snacks, Drinks & Beverages",
                "keywords": "milk, peak, danoo, milo, bournvita, cornflakes, oats, coffee, tea, fruit juice, malt, soft drink, wine, energy drink, bottled water",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Pack Quantity / Size", "required": True},
                ],
            },
            {
                "name": "Household Cleaning, Laundry & Toiletries",
                "keywords": "detergent, ariel, sunlight, dishwash, bleach, hypo, air freshener, insecticide, tissue paper, toothpaste, bathing soap",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Pack Size", "required": True},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 12. BABY, KIDS, TOYS & SCHOOL SUPPLIES
    # ------------------------------------------------------------------
    {
        "name": "Baby, Kids & Maternity",
        "keywords": "baby, diapers, pampers, huggers, baby food, stroller, walker, crib, kids clothes, school bag, toy, bicycle",
        "schema": [
            {"name": "Brand", "required": False},
            {"name": "Age Range / Size", "required": True},
        ],
        "subcategories": [
            {
                "name": "Baby Diapers, Wipes, Feeding & Nursery Gear",
                "keywords": "diapers, pampers, huggies, molfix, baby wipes, breast pump, feeding bottle, baby formula, stroller, baby walker, baby cot",
                "schema": [
                    {"name": "Brand", "required": True},
                    {"name": "Size / Age Stage", "required": True},
                ],
            },
            {
                "name": "Kids' Clothing, School Bags & Educational Toys",
                "keywords": "kids clothes, children shoes, school bag, lunch box, water bottle, lego, educational tablet, kids bicycle, board game",
                "schema": [
                    {"name": "Age Group", "required": True},
                    {"name": "Color / Size", "required": False},
                ],
            },
        ],
    },

    # ------------------------------------------------------------------
    # 13. SPORTS, FITNESS, MUSICAL INSTRUMENTS & BOOKS
    # ------------------------------------------------------------------
    {
        "name": "Sports, Fitness, Music & Books",
        "keywords": "gym, dumbbell, treadmill, jersey, football, yoga mat, guitar, keyboard, piano, drum, book, novel, stationery",
        "schema": [
            {"name": "Brand", "required": False},
            {"name": "Condition", "required": True},
        ],
        "subcategories": [
            {
                "name": "Gym Equipment, Dumbbells & Sportswear",
                "keywords": "dumbbell, barbell, treadmill, exercise bike, yoga mat, resistance band, tummy trimmer, football jersey, football boot",
                "schema": [
                    {"name": "Brand", "required": False},
                    {"name": "Weight / Size", "required": True},
                ],
            },
            {
                "name": "Musical Instruments, DJ & Live Sound Gear",
                "keywords": "keyboard piano, yamaha psr, acoustic guitar, bass guitar, drum set, saxophone, audio interface, studio mixer, dj controller, pa speaker",
                "schema": TECH_SCHEMA,
            },
            {
                "name": "Books, Textbooks, Bibles & Office Stationery",
                "keywords": "book, textbook, motivational book, bible, notebook, journal, calculator, drawing tablet, art supplies",
                "schema": [
                    {"name": "Author / Brand", "required": False},
                    {"name": "Format (Paperback / Hardcover / Pack)", "required": True},
                ],
            },
        ],
    },
]


SERVICE_CATEGORIES = [
    # ------------------------------------------------------------------
    # 1. SOLAR, INVERTER & ELECTRICAL ENGINEERING SERVICES
    # ------------------------------------------------------------------
    {
        "name": "Solar, Inverter & Electrical Engineering",
        "keywords": "solar installation, inverter installation, inverter repair, electrician, house wiring, conduit wiring, db dressing, changeover, ats, fault tracing",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Complete Solar & Inverter System Installation",
                "keywords": "solar installation, inverter setup, roof mounting, lithium battery setup, off grid solar",
                "schema": DEFAULT_SERVICE_SCHEMA + [{"name": "System Capacity Range (kVA)", "required": True}],
            },
            {
                "name": "Inverter & Charge Controller Fault Repair",
                "keywords": "inverter repair, board repair, overload fault, mppt repair, bms repair",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Solar Panel Cleaning & System Upgrade",
                "keywords": "solar cleaning, panel relocation, array upgrade, battery upgrade",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Full Building Conduit & Surface Wiring",
                "keywords": "house wiring, conduit piping, surface wiring, commercial wiring, earthing installation",
                "schema": DEFAULT_SERVICE_SCHEMA + [{"name": "Property Type (Residential / Commercial)", "required": True}],
            },
            {
                "name": "Distribution Board (DB) Upgrade & Balancing",
                "keywords": "distribution board, db dressing, load balancing, breaker replacement, surge protection",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Changeover, ATS & Generator Integration",
                "keywords": "changeover installation, automatic transfer switch, ats wiring, generator automation",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Electrical Fault Tracing & Emergency Repair",
                "keywords": "fault tracing, power outage, tripping breaker, short circuit, burnt socket repair",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 2. HVAC, PLUMBING, CARPENTRY & HOME REPAIRS
    # ------------------------------------------------------------------
    {
        "name": "AC, Plumbing, Carpentry & Home Repairs",
        "keywords": "ac installation, ac repair, plumber, borehole, carpenter, furniture, pop ceiling, painter, tiler, cctv installation, chandelier mounting",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Split & Standing AC Installation & Relocation",
                "keywords": "ac installation, split ac mounting, copper piping, ac bracket",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "AC Servicing, Gas Charging & Fridge Repair",
                "keywords": "ac servicing, gas refill, compressor repair, refrigerator repair, freezer repair",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Chandelier & POP Downlight Installation",
                "keywords": "chandelier mounting, pop light installation, led strip, smart switch setup",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "CCTV Camera, Smart Lock & Access Control Setup",
                "keywords": "cctv installation, ip camera, electric fence, intercom, smart door lock installation, starlink installation",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Plumbing, Water Heater, Pump & Borehole Repairs",
                "keywords": "plumber, pipe leak, water heater installation, pumping machine repair, toilet installation, tank washing, borehole flushing",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Carpentry, POP Ceiling, Painting & Tiling",
                "keywords": "carpenter, kitchen cabinet, wardrobe, furniture repair, painter, wallpaper, pop ceiling, tiler, aluminum window",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 3. TECH, SOFTWARE, DESIGN & GADGET REPAIR
    # ------------------------------------------------------------------
    {
        "name": "Tech, Web Development, Design & Gadget Repair",
        "keywords": "web developer, software engineer, mobile app, graphic design, logo design, flyer design, ui ux, video editing, phone repair, laptop repair",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Full-Stack Web & Mobile App Development",
                "keywords": "website design, web development, django, react, ecommerce website, mobile app development, landing page, software engineering",
                "schema": [
                    {"name": "Tech Stack / Platform", "required": True},
                    {"name": "Estimated Delivery Timeline", "required": True},
                    {"name": "Post-Launch Support Included", "required": False},
                ],
            },
            {
                "name": "Graphic Design, Brand Identity & Flyer Design",
                "keywords": "graphic designer, logo design, brand identity, church flyer, event flyer, business card, banner design, product packaging",
                "schema": [
                    {"name": "Deliverable Formats (PNG, PDF, SVG, PSD)", "required": True},
                    {"name": "Number of Revisions", "required": True},
                    {"name": "Turnaround Time", "required": True},
                ],
            },
            {
                "name": "UI/UX Design, Video Editing & Motion Graphics",
                "keywords": "ui ux design, figma, video editor, reels editing, motion graphics, 3d animation, youtube editing",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Phone, Laptop, Console & Gadget Repair",
                "keywords": "phone screen replacement, iphone repair, laptop motherboard repair, os installation, windows 11 upgrade, ps4 controller repair",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Digital Marketing, Social Media & SEO",
                "keywords": "social media manager, instagram ads, meta ads, google ads, seo, copywriting, content creation",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 4. BEAUTY, HAIR STYLING, SPA & FASHION TAILORING
    # ------------------------------------------------------------------
    {
        "name": "Beauty, Hair Salon, Spa & Fashion Tailoring",
        "keywords": "hairstylist, salon, braiding, wig installation, frontal, barber, makeup artist, gele, nail tech, pedicure, spa, massage, tailor, fashion designer",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Hair Styling, Braiding & Frontal Wig Installation",
                "keywords": "hair salon, knotless braids, boho braids, frontal installation, wig revamping, wig coloring, silk press, natural hair care, bridal hair",
                "schema": [
                    {"name": "Service Location (Salon / Home Service)", "required": True},
                    {"name": "Estimated Session Duration", "required": True},
                ],
            },
            {
                "name": "Barbing, Men's Grooming & Loc Maintenance",
                "keywords": "barber, home service barber, haircut, beard trim, dreadlock retwist, starter locs, sisterlocks",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Makeup Artistry, Gele Tying & Bridal Glam",
                "keywords": "makeup artist, mua, bridal makeup, birthday shoot makeup, gele tying, studio glam",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Nail Tech, Lashes, Brow Microblading & Spa",
                "keywords": "acrylic nails, gel extensions, pedicure, manicure, lash extensions, microblading, facial treatment, body massage, waxing",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Bespoke Tailoring, Senator & Bridal Fashion Design",
                "keywords": "tailor, fashion designer, senator sewing, agbada, asoebi, corset gown, bridal dress, clothing alteration",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 5. CLEANING, LAUNDRY, FUMIGATION & HOME CARE
    # ------------------------------------------------------------------
    {
        "name": "Cleaning, Laundry & Fumigation Services",
        "keywords": "cleaning service, post construction cleaning, sofa cleaning, rug washing, dry cleaning, laundry, fumigation, pest control",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Home, Office & Post-Construction Deep Cleaning",
                "keywords": "deep cleaning, post construction cleaning, move in cleaning, upholstery sofa cleaning, carpet cleaning",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Laundry, Dry Cleaning & Pickup Ironing",
                "keywords": "laundry, dry cleaner, wash and fold, suit dry cleaning, duvet washing",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Pest Control, Fumigation & Sanitization",
                "keywords": "fumigation, pest control, rodent control, termite treatment, bedbug extermination",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 6. EVENTS, CATERING, PHOTOGRAPHY & ENTERTAINMENT
    # ------------------------------------------------------------------
    {
        "name": "Events, Catering, Photography & Entertainment",
        "keywords": "catering, cake, baker, small chops, private chef, event planner, decorator, photographer, videographer, drone, dj, mc",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Catering, Custom Cakes, Small Chops & Private Chef",
                "keywords": "caterer, party jollof, small chops, birthday cake, wedding cake, food tray, bowl of soup, private chef",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Photography, Videography & Drone Coverage",
                "keywords": "photographer, wedding photography, portrait shoot, event videographer, drone pilot, live streaming",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Event Planning, Hall Decoration, DJ & MC",
                "keywords": "event planner, event decorator, balloon decor, dj, master of ceremony, mc, sound rental, ushers, bouncers",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 7. AUTOMOTIVE, MOTORCYCLE & LOGISTICS SERVICES
    # ------------------------------------------------------------------
    {
        "name": "Auto Care, Motorcycle Servicing & Logistics",
        "keywords": "mechanic, auto electrician, car scanner, bike servicing, car wash, auto detailing, panel beater, car painting, dispatch rider, moving truck",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Auto Mechanic, Mechatronics & OBD Diagnostics",
                "keywords": "mechanic, engine servicing, brake replacement, auto electrician, obd scanning, gear repair, ac gas car",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Motorcycle & Power Bike Servicing & Custom Mods",
                "keywords": "motorcycle mechanic, power bike servicing, oil change, chain adjustment, bike wrap, custom exhaust",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Car Wash, Interior Detailing, Wrapping & Painting",
                "keywords": "car detailing, interior buffing, ceramic coating, oven baked painting, panel beating, car tint",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Relocation, Haulage Van & Local Dispatch Errands",
                "keywords": "relocation mover, house moving truck, pickup van hire, dispatch rider, local delivery, haulage",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },

    # ------------------------------------------------------------------
    # 8. TUTORING, TECH MENTORSHIP, BUSINESS & REAL ESTATE
    # ------------------------------------------------------------------
    {
        "name": "Tutoring, Mentorship, Business & Real Estate",
        "keywords": "coding tutor, programming mentor, home lesson, ielts, waec, jamb, music lesson, cac registration, accounting, interior design, architect",
        "schema": DEFAULT_SERVICE_SCHEMA,
        "subcategories": [
            {
                "name": "Coding Mentorship, Tech Training & Computer Lessons",
                "keywords": "coding mentor, web development training, python, javascript, html css, data analysis, computer appreciation, ui ux class",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Academic Tutoring, Exam Prep & Music/Driving Lessons",
                "keywords": "home tutor, mathematics tutor, waec, jamb, ielts, french tutor, piano lesson, guitar lesson, driving school, fitness trainer",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "CAC Registration, Tax, Legal & Business Consulting",
                "keywords": "cac business registration, trademark, tax filing, business plan, cv writing, legal consultation",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
            {
                "name": "Architectural Drawing, Interior Design & Facility Management",
                "keywords": "architect, 3d architectural rendering, building plan, interior decorator, quantity surveyor, real estate inspection",
                "schema": DEFAULT_SERVICE_SCHEMA,
            },
        ],
    },
]


# Legacy top-level electrical parents that have been consolidated into
# "Electricals, Lighting & Hardware Tools" so the department sidebar stays balanced
LEGACY_ELECTRICAL_PARENTS = [
    "Cables, Wires & Conduits",
    "Circuit Protection & Switchgear",
    "Switches, Sockets & Accessories",
    "Lighting & Smart Illumination",
    "Electrical Tools & Testing Gear",
    "Residential & Commercial Electrical Wiring",
    "Lighting & Security Systems Setup",
    "HVAC & Appliance Engineering",
    "Solar & Inverter Engineering Services",
]


class Command(BaseCommand):
    help = "Seeds comprehensive AllThings product and service categories across all verticals."

    def _unique_slug(self, base_text, prefix=""):
        raw = f"{prefix}-{base_text}" if prefix else base_text
        return slugify(raw)[:95]

    def _upsert_category(self, name, cat_type, parent, slug, keywords, schema):
        """
        Safely finds an existing Category by slug or (name + category_type) so re-parenting
        existing subcategories never triggers a unique slug constraint violation.
        """
        existing = (
            Category.objects.filter(slug=slug).first()
            or Category.objects.filter(name=name, category_type=cat_type).first()
        )
        if existing:
            existing.name = name
            existing.slug = slug
            existing.parent = parent
            existing.category_type = cat_type
            existing.search_keywords = keywords
            existing.attribute_schema = schema
            existing.is_active = True
            existing.save()
            return existing, False

        new_cat = Category.objects.create(
            name=name,
            slug=slug,
            parent=parent,
            category_type=cat_type,
            search_keywords=keywords,
            attribute_schema=schema,
            is_active=True,
        )
        return new_cat, True

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding AllThings Product Departments ==="))
        for parent_data in PRODUCT_CATEGORIES:
            parent_slug = self._unique_slug(parent_data["name"], "prod")
            parent_cat, created = self._upsert_category(
                name=parent_data["name"],
                cat_type="PRODUCT",
                parent=None,
                slug=parent_slug,
                keywords=parent_data["keywords"],
                schema=parent_data.get("schema", []),
            )
            created_count += int(created)
            updated_count += int(not created)
            self.stdout.write(f"  [PRODUCT DEPT] {parent_cat.name}")

            for sub_data in parent_data.get("subcategories", []):
                sub_slug = self._unique_slug(sub_data["name"], "prod")
                sub_cat, sub_created = self._upsert_category(
                    name=sub_data["name"],
                    cat_type="PRODUCT",
                    parent=parent_cat,
                    slug=sub_slug,
                    keywords=sub_data["keywords"],
                    schema=sub_data.get("schema", parent_data.get("schema", [])),
                )
                created_count += int(sub_created)
                updated_count += int(not sub_created)
                self.stdout.write(f"     └── {sub_cat.name}")

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seeding AllThings Service Departments ==="))
        for parent_data in SERVICE_CATEGORIES:
            parent_slug = self._unique_slug(parent_data["name"], "srv")
            parent_cat, created = self._upsert_category(
                name=parent_data["name"],
                cat_type="SERVICE",
                parent=None,
                slug=parent_slug,
                keywords=parent_data["keywords"],
                schema=parent_data.get("schema", DEFAULT_SERVICE_SCHEMA),
            )
            created_count += int(created)
            updated_count += int(not created)
            self.stdout.write(f"  [SERVICE DEPT] {parent_cat.name}")

            for sub_data in parent_data.get("subcategories", []):
                sub_slug = self._unique_slug(sub_data["name"], "srv")
                sub_cat, sub_created = self._upsert_category(
                    name=sub_data["name"],
                    cat_type="SERVICE",
                    parent=parent_cat,
                    slug=sub_slug,
                    keywords=sub_data["keywords"],
                    schema=sub_data.get("schema", parent_data.get("schema", DEFAULT_SERVICE_SCHEMA)),
                )
                created_count += int(sub_created)
                updated_count += int(not sub_created)
                self.stdout.write(f"     └── {sub_cat.name}")

        # Cleanly retire old split electrical parent categories whose subcategories were consolidated
        elec_prod_parent = Category.objects.filter(name="Electricals, Lighting & Hardware Tools", parent=None).first()
        elec_srv_parent = Category.objects.filter(name="Solar, Inverter & Electrical Engineering", parent=None).first()

        for old_name in LEGACY_ELECTRICAL_PARENTS:
            old_cat = Category.objects.filter(name=old_name, parent=None).first()
            if old_cat:
                if elec_prod_parent and old_cat.category_type == "PRODUCT":
                    Product.objects.filter(category=old_cat).update(category=elec_prod_parent)
                    old_cat.subcategories.all().update(parent=elec_prod_parent)
                elif elec_srv_parent and old_cat.category_type == "SERVICE":
                    Service.objects.filter(category=old_cat).update(category=elec_srv_parent)
                    old_cat.subcategories.all().update(parent=elec_srv_parent)

                if not old_cat.products.exists() and not old_cat.services.exists() and not old_cat.subcategories.exists():
                    old_cat.delete()
                else:
                    old_cat.is_active = False
                    old_cat.save(update_fields=["is_active"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created {created_count} new categories and updated {updated_count} existing categories."
            )
        )