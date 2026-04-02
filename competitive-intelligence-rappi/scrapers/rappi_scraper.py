"""
Scraper para Rappi México (baseline propio).
Recolecta precios, fees, tiempos de entrega y promociones.
"""
import re
from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from utils.anti_detection import random_delay
from utils.logger import get_logger

log = get_logger("scraper.rappi")


class RappiScraper(BaseScraper):
    PLATFORM_NAME = "rappi"
    BASE_URL = "https://www.rappi.com.mx"

    async def set_location(self, page: Page, address: dict) -> bool:
        """Configura la ubicación en Rappi usando coordenadas o dirección."""
        try:
            # Intentar configurar dirección via URL con coordenadas
            lat, lng = address["lat"], address["lng"]
            url = f"{self.BASE_URL}/restaurantes?lat={lat}&lng={lng}"
            if not await self.safe_goto(page, url):
                return False

            await page.wait_for_load_state("networkidle", timeout=15000)

            # Verificar si se cargó la página de restaurantes
            try:
                await page.wait_for_selector(
                    '[data-qa="store-card"], .store-card, [class*="StoreCard"], [class*="restaurant"]',
                    timeout=10000
                )
                log.info(f"Ubicación configurada en Rappi: {address['name']}")
                return True
            except Exception:
                pass

            # Fallback: intentar con el buscador de dirección
            try:
                address_btn = page.locator('[data-qa="address-button"], [class*="address"], .location-button').first
                if await address_btn.is_visible(timeout=5000):
                    await address_btn.click()
                    await random_delay(0.3)

                    input_field = page.locator('input[type="text"], input[placeholder*="dirección"], input[placeholder*="address"]').first
                    if await input_field.is_visible(timeout=5000):
                        await input_field.fill(address["address"])
                        await random_delay(0.5)

                        # Seleccionar primera sugerencia
                        suggestion = page.locator('[class*="suggestion"], [class*="Suggestion"], [role="option"]').first
                        if await suggestion.is_visible(timeout=5000):
                            await suggestion.click()
                            await random_delay(1)
                            return True
            except Exception as e:
                log.debug(f"Fallback de dirección falló: {e}")

            # Si llegamos aquí, al menos la página cargó
            return True

        except Exception as e:
            log.error(f"Error configurando ubicación en Rappi: {e}")
            return False

    async def search_store(self, page: Page, store_name: str) -> bool:
        """Busca un restaurante/tienda en Rappi."""
        try:
            # Usar la barra de búsqueda
            search_selectors = [
                'input[data-qa="search-input"]',
                'input[placeholder*="Buscar"]',
                'input[placeholder*="buscar"]',
                '[data-qa="search"] input',
                'input[type="search"]',
                '.search-input input',
            ]

            search_input = None
            for selector in search_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=3000):
                        search_input = el
                        break
                except Exception:
                    continue

            if not search_input:
                # Intentar hacer clic en el ícono de búsqueda primero
                try:
                    search_icon = page.locator('[data-qa="search-icon"], [class*="search-icon"], button[aria-label*="search"]').first
                    if await search_icon.is_visible(timeout=3000):
                        await search_icon.click()
                        await random_delay(0.3)
                        search_input = page.locator('input[type="text"], input[type="search"]').first
                except Exception:
                    pass

            if not search_input:
                # Navegar directamente a búsqueda
                lat, lng = page.url.split("lat=")[-1].split("&lng=") if "lat=" in page.url else (None, None)
                search_url = f"{self.BASE_URL}/search?term={store_name.replace(' ', '%20')}"
                await self.safe_goto(page, search_url)
                await page.wait_for_load_state("networkidle", timeout=10000)
                return True

            await search_input.fill("")
            await search_input.fill(store_name)
            await random_delay(1)

            # Esperar resultados y hacer clic en el primero
            result_selectors = [
                f'text="{store_name}"',
                '[data-qa="search-result"] >> first',
                '[class*="SearchResult"]',
                '[class*="store-card"]',
            ]

            for selector in result_selectors:
                try:
                    result = page.locator(selector).first
                    if await result.is_visible(timeout=5000):
                        await result.click()
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        return True
                except Exception:
                    continue

            log.warning(f"No se encontró {store_name} en Rappi")
            return False

        except Exception as e:
            log.error(f"Error buscando {store_name} en Rappi: {e}")
            return False

    async def scrape_restaurant(self, page: Page, restaurant_name: str, products: list[dict]) -> dict:
        """Scrapea productos de un restaurante en Rappi."""
        store_data = {
            "store_name": restaurant_name,
            "platform": self.PLATFORM_NAME,
            "available": True,
            "estimated_delivery_time": None,
            "rating": None,
            "products": [],
        }

        try:
            # Extraer tiempo estimado de entrega
            delivery_selectors = [
                '[data-qa="delivery-time"]',
                '[class*="delivery-time"]',
                '[class*="DeliveryTime"]',
                '[class*="eta"]',
                'text=/\\d+\\s*-\\s*\\d+\\s*min/',
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

            # Extraer rating
            try:
                rating_el = page.locator('[data-qa="store-rating"], [class*="rating"], [class*="Rating"]').first
                if await rating_el.is_visible(timeout=3000):
                    text = await rating_el.text_content()
                    if text:
                        match = re.search(r"(\d+\.?\d*)", text)
                        if match:
                            store_data["rating"] = float(match.group(1))
            except Exception:
                pass

            # Buscar cada producto
            for product in products:
                product_data = await self._find_product(page, product)
                store_data["products"].append(product_data)

        except Exception as e:
            log.error(f"Error scrapeando restaurante {restaurant_name}: {e}")

        return store_data

    async def _find_product(self, page: Page, product: dict) -> dict:
        """Busca un producto específico en la página del restaurante."""
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
                    # Buscar por texto del producto
                    product_cards = page.locator(f'text=/{re.escape(search_term)}/i')
                    count = await product_cards.count()

                    if count > 0:
                        card = product_cards.first
                        # Navegar al contenedor padre para encontrar el precio
                        parent = card.locator("xpath=ancestor::div[contains(@class, 'product') or contains(@class, 'item') or contains(@data-qa, 'product')]").first

                        try:
                            if not await parent.is_visible(timeout=2000):
                                parent = card.locator("xpath=ancestor::div[3]")
                        except Exception:
                            parent = card.locator("xpath=ancestor::div[3]")

                        # Buscar precio en el contenedor
                        price_text = await parent.text_content()
                        if price_text:
                            prices = re.findall(r"\$\s*([\d,]+(?:\.\d{2})?)", price_text)
                            if prices:
                                product_data["found"] = True
                                product_data["available"] = True
                                product_data["price"] = float(prices[-1].replace(",", ""))
                                if len(prices) > 1:
                                    product_data["original_price"] = float(prices[0].replace(",", ""))
                                    product_data["discount"] = round(
                                        (1 - product_data["price"] / product_data["original_price"]) * 100, 1
                                    )
                                break
                except Exception:
                    continue

        except Exception as e:
            log.debug(f"Error buscando producto {product['name']}: {e}")

        return product_data

    async def scrape_fees(self, page: Page) -> dict:
        """Extrae delivery fee y service fee de Rappi."""
        fees = {
            "delivery_fee": None,
            "service_fee": None,
            "small_order_fee": None,
            "free_delivery": False,
        }

        try:
            page_text = await page.text_content("body")
            if not page_text:
                return fees

            # Delivery fee
            delivery_patterns = [
                r"[Ee]nvío[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Dd]elivery[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Cc]osto de envío[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
            ]
            for pattern in delivery_patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["delivery_fee"] = float(match.group(1).replace(",", ""))
                    break

            # Envío gratis
            if re.search(r"[Ee]nvío\s+[Gg]ratis|[Ff]ree\s+[Dd]elivery|\$\s*0\.?0{0,2}\s*envío", page_text):
                fees["free_delivery"] = True
                fees["delivery_fee"] = 0.0

            # Service fee
            service_patterns = [
                r"[Ss]ervicio[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Ss]ervice\s*[Ff]ee[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Cc]omisión[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
            ]
            for pattern in service_patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["service_fee"] = float(match.group(1).replace(",", ""))
                    break

        except Exception as e:
            log.debug(f"Error extrayendo fees de Rappi: {e}")

        return fees

    async def scrape_promotions(self, page: Page) -> list[dict]:
        """Extrae promociones visibles en Rappi."""
        promotions = []

        try:
            promo_selectors = [
                '[data-qa="promotion"], [data-qa="discount"]',
                '[class*="promo"], [class*="Promo"]',
                '[class*="discount"], [class*="Discount"]',
                '[class*="coupon"], [class*="Coupon"]',
                '[class*="banner"] [class*="offer"]',
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

            # Buscar textos de descuento en la página
            page_text = await page.text_content("body") or ""
            discount_patterns = [
                r"(\d+%\s*(?:de\s+)?(?:desc|off|descuento))",
                r"(2x1[^.]*)",
                r"(envío\s+gratis[^.]*)",
                r"(\$\d+\s+de\s+descuento[^.]*)",
            ]
            for pattern in discount_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches[:5]:
                    promotions.append({
                        "platform": self.PLATFORM_NAME,
                        "type": "discount",
                        "description": match.strip()[:200],
                    })

        except Exception as e:
            log.debug(f"Error extrayendo promociones de Rappi: {e}")

        # Deduplicar
        seen = set()
        unique = []
        for p in promotions:
            if p["description"] not in seen:
                seen.add(p["description"])
                unique.append(p)

        return unique[:20]
