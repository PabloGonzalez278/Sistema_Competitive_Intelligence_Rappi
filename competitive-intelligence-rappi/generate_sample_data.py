"""
Genera datos de muestra realistas para demostración y testing.
Útil como backup en caso de bloqueos durante la presentación en vivo.
"""
import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import DATA_DIR, CONFIG_DIR, TIMESTAMP_FORMAT


def generate_sample_data():
    """Genera datos simulados realistas basados en rangos de precios reales."""

    with open(CONFIG_DIR / "addresses.json", "r", encoding="utf-8") as f:
        addresses = json.load(f)["addresses"]

    with open(CONFIG_DIR / "products.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    platforms = {
        "rappi": {
            "price_multiplier": 1.0,
            "delivery_fee_range": (19, 49),
            "service_fee_range": (9, 25),
            "delivery_time_range": (25, 45),
            "promo_count": (1, 4),
        },
        "uber_eats": {
            "price_multiplier": 0.95,
            "delivery_fee_range": (15, 39),
            "service_fee_range": (7, 20),
            "delivery_time_range": (20, 40),
            "promo_count": (2, 6),
        },
        "didi_food": {
            "price_multiplier": 0.92,
            "delivery_fee_range": (12, 35),
            "service_fee_range": (5, 18),
            "delivery_time_range": (28, 50),
            "promo_count": (0, 3),
        },
    }

    zone_modifiers = {
        "premium": {"price": 1.15, "delivery_fee": 0.8, "time": 0.85},
        "middle_high": {"price": 1.05, "delivery_fee": 0.9, "time": 0.9},
        "middle": {"price": 1.0, "delivery_fee": 1.0, "time": 1.0},
        "business": {"price": 1.1, "delivery_fee": 0.85, "time": 0.9},
        "commercial": {"price": 1.05, "delivery_fee": 0.95, "time": 0.95},
        "university": {"price": 0.95, "delivery_fee": 1.05, "time": 1.0},
        "popular": {"price": 0.9, "delivery_fee": 1.15, "time": 1.1},
        "peripheral": {"price": 0.88, "delivery_fee": 1.3, "time": 1.25},
    }

    sample_promos = {
        "rappi": [
            "20% de descuento en tu primer pedido",
            "Envío gratis en pedidos +$200",
            "2x1 en combos seleccionados",
            "Rappi Prime: envío gratis ilimitado",
            "$50 de descuento con código RAPPI50",
        ],
        "uber_eats": [
            "30% off tu próximo pedido (máx $80)",
            "Envío gratis en restaurantes seleccionados",
            "2x1 en McFlurry",
            "Uber One: 5% de descuento + envío $0",
            "Buy 1 Get 1 Free en combos",
            "$40 off con Uber One",
        ],
        "didi_food": [
            "Envío gratis primera compra",
            "15% descuento cupón DIDI15",
            "Combo especial desde $89",
        ],
    }

    all_results = {}

    for platform_name, platform_config in platforms.items():
        platform_results = []

        for addr in addresses:
            zone = addr["zone_type"]
            zone_mod = zone_modifiers.get(zone, zone_modifiers["middle"])

            timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
            record = {
                "platform": platform_name,
                "address_id": addr["id"],
                "address_name": addr["name"],
                "address_full": addr["address"],
                "zone_type": zone,
                "coordinates": {"lat": addr["lat"], "lng": addr["lng"]},
                "timestamp": timestamp,
                "products": [],
                "fees": {},
                "promotions": [],
                "errors": [],
                "metadata": {"scraping_completed": True, "blocked": False},
            }

            # Simular scraping por categoría
            for cat_key, category in products["categories"].items():
                store_name = category.get("restaurant") or category.get("store", "")
                if not store_name:
                    continue

                # Probabilidad de encontrar la tienda
                availability_prob = 0.85 if zone not in ("peripheral",) else 0.6

                if random.random() > availability_prob:
                    record["errors"].append(f"Tienda no encontrada: {store_name}")
                    continue

                min_time, max_time = platform_config["delivery_time_range"]
                time_mod = zone_mod["time"]
                low = int(min_time * time_mod)
                high = int(max_time * time_mod)

                store_data = {
                    "store_name": store_name,
                    "platform": platform_name,
                    "available": True,
                    "estimated_delivery_time": f"{low}-{high} min",
                    "rating": round(random.uniform(3.8, 4.9), 1),
                    "products": [],
                }

                for product in category["products"]:
                    price_range = product.get("expected_price_range", {"min": 50, "max": 150})
                    base_price = random.uniform(price_range["min"], price_range["max"])
                    price = round(base_price * platform_config["price_multiplier"] * zone_mod["price"], 2)

                    has_discount = random.random() < 0.2
                    original_price = None
                    discount = None
                    if has_discount:
                        discount_pct = random.choice([10, 15, 20, 25])
                        original_price = round(price / (1 - discount_pct / 100), 2)
                        discount = discount_pct

                    store_data["products"].append({
                        "product_id": product["id"],
                        "product_name": product["name"],
                        "found": True,
                        "price": price,
                        "original_price": original_price,
                        "discount": discount,
                        "available": True,
                    })

                record["products"].append(store_data)

                # Fees
                df_min, df_max = platform_config["delivery_fee_range"]
                sf_min, sf_max = platform_config["service_fee_range"]
                delivery_fee = round(random.uniform(df_min, df_max) * zone_mod["delivery_fee"], 2)
                service_fee = round(random.uniform(sf_min, sf_max), 2)
                free_delivery = random.random() < 0.1

                record["fees"][store_name] = {
                    "delivery_fee": 0.0 if free_delivery else delivery_fee,
                    "service_fee": service_fee,
                    "small_order_fee": None,
                    "free_delivery": free_delivery,
                }

            # Promotions
            promo_min, promo_max = platform_config["promo_count"]
            n_promos = random.randint(promo_min, promo_max)
            promos = random.sample(sample_promos[platform_name], min(n_promos, len(sample_promos[platform_name])))
            for p in promos:
                record["promotions"].append({
                    "platform": platform_name,
                    "type": "promotion",
                    "description": p,
                })

            platform_results.append(record)

        all_results[platform_name] = platform_results

    # Guardar resultados
    ts = datetime.now().strftime(TIMESTAMP_FORMAT)
    output = {
        "metadata": {
            "timestamp": ts,
            "platforms": list(all_results.keys()),
            "total_records": sum(len(v) for v in all_results.values()),
            "note": "DATOS SIMULADOS PARA DEMOSTRACIÓN",
        },
        "results": all_results,
    }

    output_path = DATA_DIR / f"combined_results_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Datos de muestra generados: {output_path}")
    print(f"Total registros: {output['metadata']['total_records']}")
    print(f"Plataformas: {', '.join(all_results.keys())}")
    for p, records in all_results.items():
        print(f"  {p}: {len(records)} direcciones")

    return output_path


if __name__ == "__main__":
    generate_sample_data()
