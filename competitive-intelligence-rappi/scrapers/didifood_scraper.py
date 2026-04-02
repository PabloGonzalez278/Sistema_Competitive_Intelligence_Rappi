"""
Scraper para DiDi Food México.
Recolecta precios, fees, tiempos de entrega y promociones.
"""
import re
from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from utils.anti_detection import random_delay
from utils.logger import get_logger

log = get_logger("scraper.didi_food")


class DidiFoodScraper(BaseScraper):
    PLATFORM_NAME = "didi_food"
    BASE_URL = "https://www.didi-food.com/es-MX"

    async def set_location(self, page: Page, address: dict) -> bool:
        """Configura la ubicación en DiDi Food."""
        try:
            # DiDi Food permite navegar con coordenadas
            lat, lng = address["lat"], address["lng"]
            url = f"{self.BASE_URL}/restaurant/listing?lat={lat}&lng={lng}"
            if not await self.safe_goto(page, url):
                # Fallback a URL base
                if not await self.safe_goto(page, self.BASE_URL):
                    return False

            await page.wait_for_load_state("networkidle", timeout=15000)

            # Verificar carga
            try:
                await page.wait_for_selector(
                    '[class*="store"], [class*="restaurant"], [class*="shop-card"], a[href*="/restaurant/"]',
                    timeout=10000
                )
                log.info(f"Ubicación configurada en DiDi Food: {address['name']}")
                return True
            except Exception:
                pass

            # Fallback: input de dirección
            try:
                addr_input = page.locator(
                    'input[placeholder*="dirección"], input[placeholder*="ubicación"], '
                    'input[placeholder*="address"], input[type="text"]'
                ).first
                if await addr_input.is_visible(timeout=5000):
                    await addr_input.fill("")
                    await addr_input.fill(address["address"])
                    await random_delay(1)

                    suggestion = page.locator('[class*="suggestion"], [class*="Suggestion"], [role="option"], [class*="dropdown"] li').first
                    if await suggestion.is_visible(timeout=5000):
                        await suggestion.click()
                        await random_delay(1.5)
                        return True
            except Exception as e:
                log.debug(f"Fallback dirección DiDi Food falló: {e}")

            return True

        except Exception as e:
            log.error(f"Error configurando ubicación en DiDi Food: {e}")
            return False

    async def search_store(self, page: Page, store_name: str) -> bool:
        """Busca un restaurante en DiDi Food."""
        try:
            # Intentar búsqueda directa
            search_selectors = [
                'input[placeholder*="Buscar"]',
                'input[placeholder*="buscar"]',
                'input[type="search"]',
                'input[class*="search"]',
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

            if search_input:
                await search_input.fill("")
                await search_input.fill(store_name)
                await random_delay(1)

                # Presionar Enter o esperar sugerencias
                await search_input.press("Enter")
                await page.wait_for_load_state("networkidle", timeout=10000)
            else:
                # Navegar a URL de búsqueda
                search_url = f"{self.BASE_URL}/search?keyword={store_name.replace(' ', '%20')}"
                if not await self.safe_goto(page, search_url):
                    return False
                await page.wait_for_load_state("networkidle", timeout=10000)

            await random_delay(0.5)

            # Encontrar y hacer clic en el restaurante
            store_selectors = [
                f'text=/{re.escape(store_name)}/i',
                'a[href*="/restaurant/"]',
                '[class*="store-card"], [class*="shop-card"]',
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

            log.warning(f"No se encontró {store_name} en DiDi Food")
            return False

        except Exception as e:
            log.error(f"Error buscando {store_name} en DiDi Food: {e}")
            return False

    async def scrape_restaurant(self, page: Page, restaurant_name: str, products: list[dict]) -> dict:
        """Scrapea productos de un restaurante en DiDi Food."""
        store_data = {
            "store_name": restaurant_name,
            "platform": self.PLATFORM_NAME,
            "available": True,
            "estimated_delivery_time": None,
            "rating": None,
            "products": [],
        }

        try:
            # Tiempo de entrega
            delivery_selectors = [
                '[class*="delivery-time"], [class*="deliveryTime"]',
                '[class*="eta"], [class*="time"]',
                'text=/\\d+\\s*[-–]\\s*\\d+\\s*min/',
            ]
            for selector in delivery_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=3000):
                        text = await el.text_content()
                        if text and re.search(r"\d+\s*min", text):
                            store_data["estimated_delivery_time"] = text.strip()
                            break
                except Exception:
                    continue

            # Rating
            try:
                rating_el = page.locator('[class*="rating"], [class*="score"]').first
                if await rating_el.is_visible(timeout=3000):
                    text = await rating_el.text_content()
                    if text:
                        match = re.search(r"(\d+\.?\d*)", text)
                        if match:
                            store_data["rating"] = float(match.group(1))
            except Exception:
                pass

            # Productos
            for product in products:
                product_data = await self._find_product(page, product)
                store_data["products"].append(product_data)

        except Exception as e:
            log.error(f"Error scrapeando {restaurant_name} en DiDi Food: {e}")

        return store_data

    async def _find_product(self, page: Page, product: dict) -> dict:
        """Busca un producto en DiDi Food."""
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
                    items = page.locator(f'text=/{re.escape(search_term)}/i')
                    count = await items.count()

                    if count > 0:
                        item = items.first
                        container = item.locator(
                            "xpath=ancestor::div[contains(@class, 'product') or contains(@class, 'item') or contains(@class, 'dish')]"
                        ).first

                        try:
                            if not await container.is_visible(timeout=2000):
                                container = item.locator("xpath=ancestor::div[3]")
                        except Exception:
                            container = item.locator("xpath=ancestor::div[3]")

                        text = await container.text_content()
                        if text:
                            prices = re.findall(r"\$\s*([\d,]+(?:\.\d{2})?)", text)
                            if prices:
                                product_data["found"] = True
                                product_data["available"] = True
                                product_data["price"] = float(prices[0].replace(",", ""))
                                if len(prices) > 1:
                                    higher = max(float(p.replace(",", "")) for p in prices)
                                    lower = min(float(p.replace(",", "")) for p in prices)
                                    if higher > lower:
                                        product_data["original_price"] = higher
                                        product_data["price"] = lower
                                        product_data["discount"] = round(
                                            (1 - lower / higher) * 100, 1
                                        )
                                break
                except Exception:
                    continue

        except Exception as e:
            log.debug(f"Error buscando producto {product['name']} en DiDi Food: {e}")

        return product_data

    async def scrape_fees(self, page: Page) -> dict:
        """Extrae fees de DiDi Food."""
        fees = {
            "delivery_fee": None,
            "service_fee": None,
            "small_order_fee": None,
            "free_delivery": False,
        }

        try:
            page_text = await page.text_content("body") or ""

            # Delivery fee
            patterns = [
                r"[Ee]nvío[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Dd]elivery[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Cc]osto\s*de\s*entrega[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
            ]
            for pattern in patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["delivery_fee"] = float(match.group(1).replace(",", ""))
                    break

            if re.search(r"[Ee]nvío\s*[Gg]ratis|[Ee]ntrega\s*[Gg]ratis|\$0\.?0{0,2}\s*envío", page_text):
                fees["free_delivery"] = True
                fees["delivery_fee"] = 0.0

            # Service fee
            service_patterns = [
                r"[Ss]ervicio[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
                r"[Cc]omisión[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
            ]
            for pattern in service_patterns:
                match = re.search(pattern, page_text)
                if match:
                    fees["service_fee"] = float(match.group(1).replace(",", ""))
                    break

        except Exception as e:
            log.debug(f"Error extrayendo fees de DiDi Food: {e}")

        return fees

    async def scrape_promotions(self, page: Page) -> list[dict]:
        """Extrae promociones de DiDi Food."""
        promotions = []

        try:
            promo_selectors = [
                '[class*="promo"], [class*="Promo"]',
                '[class*="discount"], [class*="Discount"]',
                '[class*="offer"], [class*="coupon"]',
                '[class*="banner"]',
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

            page_text = await page.text_content("body") or ""
            patterns = [
                r"(\d+%\s*(?:de\s+)?(?:desc|off|descuento)[^.]{0,50})",
                r"(2x1[^.]{0,50})",
                r"([Ee]nvío\s+[Gg]ratis[^.]{0,50})",
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
            log.debug(f"Error extrayendo promociones de DiDi Food: {e}")

        seen = set()
        unique = []
        for p in promotions:
            if p["description"] not in seen:
                seen.add(p["description"])
                unique.append(p)

        return unique[:20]
