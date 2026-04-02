"""
Scraper para Uber Eats México.
Recolecta precios, fees, tiempos de entrega y promociones.
"""
import re
from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from utils.anti_detection import random_delay
from utils.logger import get_logger

log = get_logger("scraper.uber_eats")


class UberEatsScraper(BaseScraper):
    PLATFORM_NAME = "uber_eats"
    BASE_URL = "https://www.ubereats.com/mx"

    async def set_location(self, page: Page, address: dict) -> bool:
        """Configura la ubicación en Uber Eats."""
        try:
            # Navegar con parámetros de ubicación
            url = f"{self.BASE_URL}/feed?diningMode=DELIVERY&pl={address['lat']}%2C{address['lng']}"
            if not await self.safe_goto(page, url):
                return False

            await page.wait_for_load_state("networkidle", timeout=15000)

            # Verificar si se cargó el feed
            try:
                await page.wait_for_selector(
                    '[data-testid="store-card"], [class*="StoreCard"], a[href*="/store/"]',
                    timeout=10000
                )
                log.info(f"Ubicación configurada en Uber Eats: {address['name']}")
                return True
            except Exception:
                pass

            # Fallback: usar el input de dirección
            try:
                # Buscar botón de dirección
                addr_btn = page.locator('button[data-testid="address-selector"], [data-testid="location-typeahead"]').first
                if await addr_btn.is_visible(timeout=5000):
                    await addr_btn.click()
                    await random_delay(0.3)

                addr_input = page.locator('input[data-testid="location-typeahead-input"], input[placeholder*="address"], input[placeholder*="dirección"]').first
                if await addr_input.is_visible(timeout=5000):
                    await addr_input.fill("")
                    await addr_input.fill(address["address"])
                    await random_delay(1)

                    suggestion = page.locator('[data-testid="location-typeahead-suggestion"], [role="option"]').first
                    if await suggestion.is_visible(timeout=5000):
                        await suggestion.click()
                        await random_delay(1.5)
                        return True
            except Exception as e:
                log.debug(f"Fallback de dirección Uber Eats falló: {e}")

            return True

        except Exception as e:
            log.error(f"Error configurando ubicación en Uber Eats: {e}")
            return False

    async def search_store(self, page: Page, store_name: str) -> bool:
        """Busca un restaurante en Uber Eats."""
        try:
            # Navegar a la URL de búsqueda directamente
            search_url = f"{self.BASE_URL}/search?q={store_name.replace(' ', '%20')}"
            if not await self.safe_goto(page, search_url):
                return False

            await page.wait_for_load_state("networkidle", timeout=10000)
            await random_delay(0.5)

            # Buscar el resultado del restaurante
            store_selectors = [
                f'a[href*="/store/"]:has-text("{store_name}")',
                '[data-testid="store-card"]',
                'a[href*="/store/"]',
            ]

            for selector in store_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=5000):
                        await el.click()
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        return True
                except Exception:
                    continue

            log.warning(f"No se encontró {store_name} en Uber Eats")
            return False

        except Exception as e:
            log.error(f"Error buscando {store_name} en Uber Eats: {e}")
            return False

    async def scrape_restaurant(self, page: Page, restaurant_name: str, products: list[dict]) -> dict:
        """Scrapea productos de un restaurante en Uber Eats."""
        store_data = {
            "store_name": restaurant_name,
            "platform": self.PLATFORM_NAME,
            "available": True,
            "estimated_delivery_time": None,
            "rating": None,
            "products": [],
        }

        try:
            # Tiempo estimado de entrega
            delivery_selectors = [
                '[data-testid="store-delivery-time"]',
                '[class*="deliveryTime"]',
                'text=/\\d+\\s*[-–]\\s*\\d+\\s*min/',
            ]
            for selector in delivery_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=3000):
                        text = await el.text_content()
                        store_data["estimated_delivery_time"] = text.strip() if text else None
                        break
                except Exception:
                    continue

            # Rating
            try:
                rating_el = page.locator('[data-testid="store-rating"], [class*="rating"]').first
                if await rating_el.is_visible(timeout=3000):
                    text = await rating_el.text_content()
                    if text:
                        match = re.search(r"(\d+\.?\d*)", text)
                        if match:
                            store_data["rating"] = float(match.group(1))
            except Exception:
                pass

            # Buscar productos
            for product in products:
                product_data = await self._find_product(page, product)
                store_data["products"].append(product_data)

        except Exception as e:
            log.error(f"Error scrapeando {restaurant_name} en Uber Eats: {e}")

        return store_data

    async def _find_product(self, page: Page, product: dict) -> dict:
        """Busca un producto en la página del restaurante de Uber Eats."""
        product_data = {
            "product_id": product["id"],
            "product_name": product["name"],
            "found": False,
            "price": None,
            "original_price": None,
            "discount": None,
            "available": False,
        }

        try:
            for search_term in product["search_terms"]:
                try:
                    # Uber Eats estructura sus productos en cards/items
                    items = page.locator(f'text=/{re.escape(search_term)}/i')
                    count = await items.count()

                    if count > 0:
                        item = items.first
                        # Buscar contenedor padre del producto
                        container = item.locator(
                            "xpath=ancestor::li[1] | ancestor::div[contains(@data-testid, 'menu-item') or contains(@class, 'menu-item')]"
                        ).first

                        try:
                            if not await container.is_visible(timeout=2000):
                                container = item.locator("xpath=ancestor::div[4]")
                        except Exception:
                            container = item.locator("xpath=ancestor::div[4]")

                        text = await container.text_content()
                        if text:
                            prices = re.findall(r"\$\s*([\d,]+(?:\.\d{2})?)", text)
                            if prices:
                                product_data["found"] = True
                                product_data["available"] = True
                                product_data["price"] = float(prices[0].replace(",", ""))
                                if len(prices) > 1:
                                    product_data["original_price"] = float(prices[1].replace(",", ""))
                                    if product_data["original_price"] > product_data["price"]:
                                        product_data["original_price"], product_data["price"] = (
                                            product_data["price"], product_data["original_price"]
                                        )
                                        product_data["price"], product_data["original_price"] = (
                                            product_data["original_price"], product_data["price"]
                                        )
                                        product_data["discount"] = round(
                                            (1 - product_data["price"] / product_data["original_price"]) * 100, 1
                                        )
                                break
                except Exception:
                    continue

        except Exception as e:
            log.debug(f"Error buscando producto {product['name']} en Uber Eats: {e}")

        return product_data

    async def scrape_fees(self, page: Page) -> dict:
        """Extrae fees de Uber Eats."""
        fees = {
            "delivery_fee": None,
            "service_fee": None,
            "small_order_fee": None,
            "free_delivery": False,
        }

        try:
            page_text = await page.text_content("body") or ""

            # Delivery fee
            delivery_patterns = [
                r"[Dd]elivery\s*[Ff]ee[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Cc]osto\s*de\s*envío[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Ee]nvío[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"\$\s*([\d,]+(?:\.\d{2})?)\s*[Dd]elivery",
            ]
            for pattern in delivery_patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["delivery_fee"] = float(match.group(1).replace(",", ""))
                    break

            # Free delivery
            if re.search(r"\$0\.?0{0,2}\s*[Dd]elivery|[Ee]ntrega\s*[Gg]ratis|[Ff]ree\s*[Dd]elivery", page_text):
                fees["free_delivery"] = True
                fees["delivery_fee"] = 0.0

            # Service fee
            service_patterns = [
                r"[Ss]ervice\s*[Ff]ee[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Cc]argo\s*por\s*servicio[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
            ]
            for pattern in service_patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["service_fee"] = float(match.group(1).replace(",", ""))
                    break

            # Small order fee
            small_patterns = [
                r"[Ss]mall\s*[Oo]rder\s*[Ff]ee[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Pp]edido\s*mínimo[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
            ]
            for pattern in small_patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["small_order_fee"] = float(match.group(1).replace(",", ""))
                    break

        except Exception as e:
            log.debug(f"Error extrayendo fees de Uber Eats: {e}")

        return fees

    async def scrape_promotions(self, page: Page) -> list[dict]:
        """Extrae promociones visibles en Uber Eats."""
        promotions = []

        try:
            promo_selectors = [
                '[data-testid*="promo"], [data-testid*="deal"]',
                '[class*="promo"], [class*="Promo"]',
                '[class*="discount"], [class*="deal"]',
                '[class*="offer"], [class*="Offer"]',
            ]

            for selector in promo_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    for i in range(min(count, 10)):
                        text = await elements.nth(i).text_content()
                        if text and len(text.strip()) > 3:
                            promotions.append({
                                "platform": self.PLATFORM_NAME,
                                "type": "promotion",
                                "description": text.strip()[:200],
                            })
                except Exception:
                    continue

            # Patrones de descuento en texto
            page_text = await page.text_content("body") or ""
            patterns = [
                r"(\d+%\s*off[^.]{0,50})",
                r"(Buy\s+\d+,?\s+get\s+\d+[^.]{0,50})",
                r"(\$\d+\s+off[^.]{0,50})",
                r"([Ee]nvío\s+[Gg]ratis[^.]{0,50})",
                r"(2x1[^.]{0,50})",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for m in matches[:3]:
                    promotions.append({
                        "platform": self.PLATFORM_NAME,
                        "type": "discount",
                        "description": m.strip()[:200],
                    })

        except Exception as e:
            log.debug(f"Error extrayendo promociones de Uber Eats: {e}")

        seen = set()
        unique = []
        for p in promotions:
            if p["description"] not in seen:
                seen.add(p["description"])
                unique.append(p)

        return unique[:20]
