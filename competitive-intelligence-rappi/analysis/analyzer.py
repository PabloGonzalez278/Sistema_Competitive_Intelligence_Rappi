"""
Motor de análisis competitivo.
Procesa los datos recolectados y genera insights accionables.
"""
import json
from collections import defaultdict
from statistics import mean, median, stdev
from utils.logger import get_logger

log = get_logger("analysis")


class CompetitiveAnalyzer:
    """Analiza datos de scraping y genera insights competitivos."""

    def __init__(self, results: dict[str, list[dict]]):
        self.results = results
        self.platforms = list(results.keys())

    def run_full_analysis(self) -> dict:
        """Ejecuta el análisis completo y retorna estructura de resultados."""
        log.info("Ejecutando análisis competitivo completo...")

        analysis = {
            "summary": self._generate_summary(),
            "price_comparison": self._analyze_prices(),
            "fee_comparison": self._analyze_fees(),
            "delivery_time_comparison": self._analyze_delivery_times(),
            "promotion_analysis": self._analyze_promotions(),
            "geographic_analysis": self._analyze_by_zone(),
            "availability_analysis": self._analyze_availability(),
            "top_insights": [],
        }

        analysis["top_insights"] = self._generate_top_insights(analysis)

        log.info(f"Análisis completado: {len(analysis['top_insights'])} insights generados")
        return analysis

    def _generate_summary(self) -> dict:
        """Genera resumen general del scraping."""
        summary = {
            "platforms_analyzed": self.platforms,
            "total_addresses": 0,
            "data_coverage": {},
        }

        for platform, records in self.results.items():
            total = len(records)
            successful = sum(1 for r in records if not r.get("errors") or len(r.get("errors", [])) == 0)
            products_found = 0
            for r in records:
                for store in r.get("products", []):
                    products_found += sum(1 for p in store.get("products", []) if p.get("found"))

            summary["data_coverage"][platform] = {
                "total_addresses": total,
                "successful_scrapes": successful,
                "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
                "products_found": products_found,
            }
            summary["total_addresses"] = max(summary["total_addresses"], total)

        return summary

    def _analyze_prices(self) -> dict:
        """Análisis comparativo de precios entre plataformas."""
        price_data = defaultdict(lambda: defaultdict(list))

        for platform, records in self.results.items():
            for record in records:
                for store in record.get("products", []):
                    store_name = store.get("store_name", "unknown")
                    for product in store.get("products", []):
                        if product.get("found") and product.get("price"):
                            key = f"{store_name}|{product['product_name']}"
                            price_data[key][platform].append(product["price"])

        comparison = {}
        for product_key, platform_prices in price_data.items():
            store_name, product_name = product_key.split("|", 1)
            avg_prices = {}
            for platform, prices in platform_prices.items():
                avg_prices[platform] = {
                    "avg": round(mean(prices), 2),
                    "min": round(min(prices), 2),
                    "max": round(max(prices), 2),
                    "median": round(median(prices), 2),
                    "count": len(prices),
                }

            # Determinar la plataforma más barata y más cara
            platforms_with_avg = {p: v["avg"] for p, v in avg_prices.items()}
            cheapest = min(platforms_with_avg, key=platforms_with_avg.get) if platforms_with_avg else None
            most_expensive = max(platforms_with_avg, key=platforms_with_avg.get) if platforms_with_avg else None

            rappi_price = platforms_with_avg.get("rappi")
            rappi_position = "N/A"
            if rappi_price and len(platforms_with_avg) > 1:
                sorted_prices = sorted(platforms_with_avg.items(), key=lambda x: x[1])
                position = [p for p, _ in sorted_prices].index("rappi") + 1
                rappi_position = f"{position}/{len(sorted_prices)}"

            comparison[product_key] = {
                "store": store_name,
                "product": product_name,
                "prices_by_platform": avg_prices,
                "cheapest_platform": cheapest,
                "most_expensive_platform": most_expensive,
                "rappi_position": rappi_position,
                "price_spread_pct": self._calc_spread(platforms_with_avg),
            }

        return comparison

    def _analyze_fees(self) -> dict:
        """Análisis comparativo de fees."""
        fee_data = defaultdict(lambda: {"delivery_fees": [], "service_fees": []})

        for platform, records in self.results.items():
            for record in records:
                for store_name, fees in record.get("fees", {}).items():
                    if fees.get("delivery_fee") is not None:
                        fee_data[platform]["delivery_fees"].append(fees["delivery_fee"])
                    if fees.get("service_fee") is not None:
                        fee_data[platform]["service_fees"].append(fees["service_fee"])

        comparison = {}
        for platform, fees in fee_data.items():
            delivery = fees["delivery_fees"]
            service = fees["service_fees"]
            comparison[platform] = {
                "delivery_fee": {
                    "avg": round(mean(delivery), 2) if delivery else None,
                    "min": round(min(delivery), 2) if delivery else None,
                    "max": round(max(delivery), 2) if delivery else None,
                    "median": round(median(delivery), 2) if delivery else None,
                    "free_delivery_pct": round(sum(1 for d in delivery if d == 0) / len(delivery) * 100, 1) if delivery else 0,
                    "count": len(delivery),
                },
                "service_fee": {
                    "avg": round(mean(service), 2) if service else None,
                    "min": round(min(service), 2) if service else None,
                    "max": round(max(service), 2) if service else None,
                    "count": len(service),
                },
            }

        return comparison

    def _analyze_delivery_times(self) -> dict:
        """Análisis de tiempos de entrega."""
        import re
        time_data = defaultdict(list)

        for platform, records in self.results.items():
            for record in records:
                for store in record.get("products", []):
                    time_str = store.get("estimated_delivery_time")
                    if time_str:
                        # Extraer minutos del string (ej: "25-35 min" -> avg 30)
                        numbers = re.findall(r"(\d+)", time_str)
                        if numbers:
                            nums = [int(n) for n in numbers]
                            avg_time = mean(nums)
                            time_data[platform].append({
                                "raw": time_str,
                                "avg_minutes": avg_time,
                                "zone": record.get("zone_type", "unknown"),
                                "address": record.get("address_name", "unknown"),
                            })

        comparison = {}
        for platform, times in time_data.items():
            minutes = [t["avg_minutes"] for t in times]
            comparison[platform] = {
                "avg_minutes": round(mean(minutes), 1) if minutes else None,
                "min_minutes": round(min(minutes), 1) if minutes else None,
                "max_minutes": round(max(minutes), 1) if minutes else None,
                "median_minutes": round(median(minutes), 1) if minutes else None,
                "count": len(minutes),
                "by_zone": self._group_times_by_zone(times),
            }

        return comparison

    def _analyze_promotions(self) -> dict:
        """Análisis de estrategias promocionales."""
        promo_data = defaultdict(list)

        for platform, records in self.results.items():
            for record in records:
                for promo in record.get("promotions", []):
                    promo_data[platform].append(promo)

        comparison = {}
        for platform, promos in promo_data.items():
            types = defaultdict(int)
            for p in promos:
                types[p.get("type", "unknown")] += 1

            comparison[platform] = {
                "total_promotions": len(promos),
                "unique_promotions": len({p["description"] for p in promos}),
                "by_type": dict(types),
                "sample_promotions": [p["description"] for p in promos[:10]],
            }

        return comparison

    def _analyze_by_zone(self) -> dict:
        """Análisis de variabilidad geográfica."""
        zone_data = defaultdict(lambda: defaultdict(lambda: {"prices": [], "fees": [], "times": []}))
        import re

        for platform, records in self.results.items():
            for record in records:
                zone = record.get("zone_type", "unknown")

                # Precios
                for store in record.get("products", []):
                    for product in store.get("products", []):
                        if product.get("found") and product.get("price"):
                            zone_data[zone][platform]["prices"].append(product["price"])

                # Fees
                for _, fees in record.get("fees", {}).items():
                    if fees.get("delivery_fee") is not None:
                        zone_data[zone][platform]["fees"].append(fees["delivery_fee"])

                # Tiempos
                for store in record.get("products", []):
                    time_str = store.get("estimated_delivery_time")
                    if time_str:
                        numbers = re.findall(r"(\d+)", time_str)
                        if numbers:
                            zone_data[zone][platform]["times"].append(mean(int(n) for n in numbers))

        comparison = {}
        for zone, platforms in zone_data.items():
            zone_analysis = {}
            for platform, data in platforms.items():
                zone_analysis[platform] = {
                    "avg_price": round(mean(data["prices"]), 2) if data["prices"] else None,
                    "avg_delivery_fee": round(mean(data["fees"]), 2) if data["fees"] else None,
                    "avg_delivery_time": round(mean(data["times"]), 1) if data["times"] else None,
                    "data_points": len(data["prices"]),
                }
            comparison[zone] = zone_analysis

        return comparison

    def _analyze_availability(self) -> dict:
        """Análisis de disponibilidad de tiendas/productos."""
        availability = defaultdict(lambda: {"stores_found": 0, "stores_not_found": 0, "products_found": 0, "products_not_found": 0})

        for platform, records in self.results.items():
            for record in records:
                for store in record.get("products", []):
                    if store.get("products"):
                        availability[platform]["stores_found"] += 1
                        for p in store["products"]:
                            if p.get("found"):
                                availability[platform]["products_found"] += 1
                            else:
                                availability[platform]["products_not_found"] += 1

                for error in record.get("errors", []):
                    if "no encontrad" in error.lower() or "not found" in error.lower():
                        availability[platform]["stores_not_found"] += 1

        result = {}
        for platform, data in availability.items():
            total_stores = data["stores_found"] + data["stores_not_found"]
            total_products = data["products_found"] + data["products_not_found"]
            result[platform] = {
                **data,
                "store_availability_rate": round(data["stores_found"] / total_stores * 100, 1) if total_stores > 0 else 0,
                "product_availability_rate": round(data["products_found"] / total_products * 100, 1) if total_products > 0 else 0,
            }

        return result

    def _generate_top_insights(self, analysis: dict) -> list[dict]:
        """Genera los Top 5 insights accionables basados en el análisis."""
        insights = []

        # Insight 1: Posicionamiento de precios
        price_comp = analysis.get("price_comparison", {})
        rappi_cheaper = 0
        rappi_expensive = 0
        total_products = 0
        for key, data in price_comp.items():
            total_products += 1
            if data.get("cheapest_platform") == "rappi":
                rappi_cheaper += 1
            if data.get("most_expensive_platform") == "rappi":
                rappi_expensive += 1

        if total_products > 0:
            insights.append({
                "id": 1,
                "category": "Pricing",
                "finding": f"Rappi es la plataforma más barata en {rappi_cheaper}/{total_products} productos "
                           f"y la más cara en {rappi_expensive}/{total_products} productos analizados.",
                "impact": "El posicionamiento de precios afecta directamente la conversión y retención de usuarios. "
                          "En un mercado price-sensitive como México, cada punto porcentual de diferencia impacta el GMV.",
                "recommendation": "Revisar la estrategia de markup por categoría. Para productos donde Rappi es más caro, "
                                  "evaluar negociación con merchants o ajuste de comisiones para cerrar la brecha de precios.",
            })

        # Insight 2: Fees comparativos
        fee_comp = analysis.get("fee_comparison", {})
        rappi_fees = fee_comp.get("rappi", {})
        competitor_fees = {k: v for k, v in fee_comp.items() if k != "rappi"}

        if rappi_fees and competitor_fees:
            rappi_avg_delivery = rappi_fees.get("delivery_fee", {}).get("avg")
            if rappi_avg_delivery is not None:
                lower_fees = [p for p, d in competitor_fees.items()
                              if d.get("delivery_fee", {}).get("avg") is not None
                              and d["delivery_fee"]["avg"] < rappi_avg_delivery]

                if lower_fees:
                    diff_pcts = []
                    for p in lower_fees:
                        comp_avg = competitor_fees[p]["delivery_fee"]["avg"]
                        diff_pcts.append(round((rappi_avg_delivery - comp_avg) / rappi_avg_delivery * 100, 1))

                    insights.append({
                        "id": 2,
                        "category": "Fees",
                        "finding": f"Los delivery fees de Rappi son más altos que {', '.join(lower_fees)} "
                                   f"en promedio ({', '.join(f'{d}%' for d in diff_pcts)} respectivamente).",
                        "impact": "Los delivery fees son un factor decisivo en la elección de plataforma. "
                                  "Usuarios comparan fees antes de completar el pedido.",
                        "recommendation": "Considerar subsidiar delivery fees en zonas de alta competencia. "
                                          "Implementar delivery fee dinámico basado en la competencia local.",
                    })

        # Insight 3: Tiempos de entrega por zona
        delivery_comp = analysis.get("delivery_time_comparison", {})
        if delivery_comp:
            times_by_platform = {p: d.get("avg_minutes") for p, d in delivery_comp.items() if d.get("avg_minutes")}
            if times_by_platform and "rappi" in times_by_platform:
                rappi_time = times_by_platform["rappi"]
                faster = [p for p, t in times_by_platform.items() if p != "rappi" and t < rappi_time]
                if faster:
                    insights.append({
                        "id": 3,
                        "category": "Operations",
                        "finding": f"Los tiempos de entrega de Rappi ({rappi_time:.0f} min promedio) son más lentos que "
                                   f"{', '.join(faster)} ({', '.join(f'{times_by_platform[p]:.0f} min' for p in faster)}).",
                        "impact": "Tiempos de entrega más largos reducen el NPS y la tasa de recompra. "
                                  "Cada minuto adicional incrementa la probabilidad de cancelación.",
                        "recommendation": "Optimizar asignación de repartidores en zonas con mayor diferencia. "
                                          "Considerar batching inteligente y rutas optimizadas con IA.",
                    })
                else:
                    insights.append({
                        "id": 3,
                        "category": "Operations",
                        "finding": f"Rappi tiene tiempos de entrega competitivos ({rappi_time:.0f} min promedio), "
                                   f"similar o mejor que la competencia.",
                        "impact": "La ventaja operacional en tiempos de entrega es un diferenciador clave para retención.",
                        "recommendation": "Mantener la ventaja operacional. Comunicar los tiempos rápidos como diferenciador en marketing.",
                    })

        # Insight 4: Variabilidad geográfica
        geo_analysis = analysis.get("geographic_analysis", {})
        if geo_analysis:
            zone_insights = []
            for zone, platforms_data in geo_analysis.items():
                rappi_data = platforms_data.get("rappi", {})
                if rappi_data.get("avg_price"):
                    for comp, comp_data in platforms_data.items():
                        if comp != "rappi" and comp_data.get("avg_price"):
                            diff = ((rappi_data["avg_price"] - comp_data["avg_price"]) / comp_data["avg_price"]) * 100
                            if abs(diff) > 10:
                                zone_insights.append((zone, comp, diff))

            if zone_insights:
                worst_zone = max(zone_insights, key=lambda x: x[2]) if zone_insights else None
                if worst_zone:
                    insights.append({
                        "id": 4,
                        "category": "Geographic Strategy",
                        "finding": f"En zonas tipo '{worst_zone[0]}', Rappi es {worst_zone[2]:.1f}% más caro que "
                                   f"{worst_zone[1]}. La competitividad varía significativamente por zona.",
                        "impact": "Las diferencias de precio por zona sugieren oportunidades de pricing localizado. "
                                  "Zonas periféricas y populares son más price-sensitive.",
                        "recommendation": f"Implementar pricing diferenciado por zona. Priorizar subsidios en zonas "
                                          f"tipo '{worst_zone[0]}' donde la brecha competitiva es mayor.",
                    })

        # Insight 5: Estrategia promocional
        promo_analysis = analysis.get("promotion_analysis", {})
        if promo_analysis:
            rappi_promos = promo_analysis.get("rappi", {}).get("total_promotions", 0)
            competitor_promos = {p: d.get("total_promotions", 0)
                                for p, d in promo_analysis.items() if p != "rappi"}
            max_comp = max(competitor_promos.items(), key=lambda x: x[1]) if competitor_promos else None

            if max_comp and max_comp[1] > rappi_promos:
                insights.append({
                    "id": 5,
                    "category": "Promotions",
                    "finding": f"Rappi tiene {rappi_promos} promociones visibles vs {max_comp[1]} de {max_comp[0]}. "
                               f"La competencia está siendo más agresiva en descuentos.",
                    "impact": "Las promociones visibles impactan directamente en la elección de plataforma "
                              "al momento de abrir la app.",
                    "recommendation": "Aumentar visibilidad de promociones en home feed. Evaluar campañas de descuento "
                                      "focalizadas en categorías y zonas donde la competencia es más agresiva.",
                })
            else:
                insights.append({
                    "id": 5,
                    "category": "Promotions",
                    "finding": f"Rappi tiene una presencia promocional competitiva con {rappi_promos} promociones visibles.",
                    "impact": "Mantener presencia promocional fuerte ayuda a retener usuarios y capturar demanda incremental.",
                    "recommendation": "Optimizar el mix de promociones. Priorizar descuentos en productos de alta elasticidad "
                                      "y zonas donde la competencia está ganando share.",
                })

        # Asegurar al menos 5 insights
        while len(insights) < 5:
            insights.append({
                "id": len(insights) + 1,
                "category": "Data Quality",
                "finding": "Se requieren más datos para generar insights adicionales con alta confianza.",
                "impact": "La calidad del análisis mejora con mayor volumen de datos y scrapes recurrentes.",
                "recommendation": "Ejecutar el scraper en múltiples horarios y días para capturar variabilidad temporal.",
            })

        return insights[:5]

    def _calc_spread(self, prices: dict[str, float]) -> float | None:
        """Calcula el spread porcentual entre precios."""
        if len(prices) < 2:
            return None
        values = list(prices.values())
        return round((max(values) - min(values)) / min(values) * 100, 1)

    def _group_times_by_zone(self, times: list[dict]) -> dict:
        """Agrupa tiempos de entrega por zona."""
        by_zone = defaultdict(list)
        for t in times:
            by_zone[t["zone"]].append(t["avg_minutes"])

        return {
            zone: {"avg": round(mean(mins), 1), "count": len(mins)}
            for zone, mins in by_zone.items()
        }
