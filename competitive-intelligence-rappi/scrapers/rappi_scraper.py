"""
Scraper para Rappi México (baseline propio).
Estrategia: Intercepta las APIs internas de Rappi que el frontend consume.
Esto es más robusto que depender de selectores CSS de una SPA.
"""
import re
import json
import asyncio
from playwright.async_api import Page, Response

from scrapers.base_scraper import BaseScraper
from utils.anti_detection import random_delay
from utils.logger import get_logger

log = get_logger("scraper.rappi")


class RappiScraper(BaseScraper):
    PLATFORM_NAME = "rappi"
    BASE_URL = "https://www.rappi.com.mx"

    def __init__(self):
        super().__init__()
        self._api_responses: list[dict] = []
        self._store_data_cache: dict = {}

    async def _capture_api_responses(self, response: Response) -> None:
        """Captura respuestas API del backend de Rappi."""
        try:
            url = response.url
            if response.status == 200 and ("api" in url or "services" in url or "grpc" in url):
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "grpc" in content_type:
                    try:
                        body = await response.json()
                        self._api_responses.append({
                            "url": url,
                            "data": body,
                        })
                    except Exception:
                        pass
        except Exception:
            pass

    async def set_location(self, page: Page, address: dict) -> bool:
        """Configura la ubicación en Rappi usando coordenadas via URL."""
        try:
            self._api_responses = []
            page.on("response", self._capture_api_responses)

            lat, lng = address["lat"], address["lng"]
            url = f"{self.BASE_URL}/restaurantes?lat={lat}&lng={lng}"
            if not await self.safe_goto(page, url):
                return False

            # Esperar a que la página cargue y las APIs respondan
            await page.wait_for_load_state("networkidle", timeout=20000)
            await asyncio.sleep(3)  # Dar tiempo extra para APIs asíncronas

            log.info(f"Ubicación configurada en Rappi: {address['name']} (APIs capturadas: {len(self._api_responses)})")
            return True

        except Exception as e:
            log.error(f"Error configurando ubicación en Rappi: {e}")
            return True  # Continuar aunque haya timeout — quizás capturamos APIs

    async def search_store(self, page: Page, store_name: str) -> bool:
        """Busca restaurante en Rappi — navega a URL de búsqueda y captura APIs."""
        try:
            self._api_responses = []
            search_term = store_name.split("/")[0].strip()  # "OXXO / Tienda..." -> "OXXO"

            # Navegar directamente a la URL de búsqueda
            search_url = f"{self.BASE_URL}/search?term={search_term.replace(' ', '%20')}"
            await self.safe_goto(page, search_url)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(3)

            # Intentar también con la barra de búsqueda si está visible
            try:
                search_input = page.locator('input[type="search"], input[data-qa="input"], input[role="searchbox"]').first
                if await search_input.is_visible(timeout=3000):
                    await search_input.click()
                    await asyncio.sleep(0.5)
                    await search_input.fill(search_term)
                    await asyncio.sleep(2)
                    # Presionar Enter
                    await search_input.press("Enter")
                    await asyncio.sleep(3)
            except Exception:
                pass

            # Extraer datos de las APIs capturadas
            self._extract_store_from_apis(store_name)

            if self._store_data_cache:
                log.info(f"Datos de {store_name} capturados via API en Rappi")
                return True

            # Fallback: extraer datos visibles del DOM
            return await self._extract_from_dom(page, store_name)

        except Exception as e:
            log.error(f"Error buscando {store_name} en Rappi: {e}")
            return False

    def _extract_store_from_apis(self, store_name: str) -> None:
        """Extrae datos de tienda de las respuestas API capturadas."""
        search_lower = store_name.lower().split("/")[0].strip()

        for api_resp in self._api_responses:
            data = api_resp.get("data")
            if not data:
                continue

            # Buscar en diferentes estructuras de respuesta API de Rappi
            stores = []
            if isinstance(data, dict):
                # Buscar en keys comunes de la API de Rappi
                for key in ["stores", "restaurants", "data", "results", "items", "components"]:
                    if key in data:
                        val = data[key]
                        if isinstance(val, list):
                            stores.extend(val)
                        elif isinstance(val, dict):
                            for sub_key in ["stores", "restaurants", "items", "data"]:
                                if sub_key in val and isinstance(val[sub_key], list):
                                    stores.extend(val[sub_key])
            elif isinstance(data, list):
                stores = data

            for store in stores:
                if not isinstance(store, dict):
                    continue
                name = store.get("name", "") or store.get("store_name", "") or store.get("title", "")
                if search_lower in name.lower():
                    self._store_data_cache = store
                    return

    async def _extract_from_dom(self, page: Page, store_name: str) -> bool:
        """Fallback: extrae datos directamente del DOM."""
        try:
            # Intentar obtener texto completo de la página
            body_text = await page.evaluate("() => document.body?.innerText || ''")
            if store_name.split("/")[0].strip().lower() in body_text.lower():
                self._store_data_cache = {"_dom_text": body_text, "_source": "dom"}
                return True

            # Intentar hacer clic en el primer resultado de búsqueda
            result_selectors = [
                'a[href*="/restaurantes/"]',
                'a[href*="/store/"]',
                '[data-qa*="store"]',
                '[class*="store-card"]',
                '[class*="StoreCard"]',
            ]
            for selector in result_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=3000):
                        await el.click()
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        await asyncio.sleep(2)
                        body_text = await page.evaluate("() => document.body?.innerText || ''")
                        self._store_data_cache = {"_dom_text": body_text, "_source": "dom"}
                        return True
                except Exception:
                    continue

        except Exception as e:
            log.debug(f"Fallback DOM falló: {e}")

        return False

    async def scrape_restaurant(self, page: Page, restaurant_name: str, products: list[dict]) -> dict:
        """Scrapea datos de un restaurante en Rappi usando APIs + DOM."""
        store_data = {
            "store_name": restaurant_name,
            "platform": self.PLATFORM_NAME,
            "available": True,
            "estimated_delivery_time": None,
            "rating": None,
            "products": [],
        }

        try:
            cache = self._store_data_cache

            # Extraer datos de API si disponibles
            if cache and "_dom_text" not in cache:
                store_data["estimated_delivery_time"] = (
                    cache.get("delivery_time_text")
                    or cache.get("delivery_eta")
                    or cache.get("eta")
                    or cache.get("delivery_time")
                )
                store_data["rating"] = cache.get("rating") or cache.get("score") or cache.get("user_rating")
                if isinstance(store_data["rating"], str):
                    match = re.search(r"(\d+\.?\d*)", str(store_data["rating"]))
                    store_data["rating"] = float(match.group(1)) if match else None

            # Extraer datos del DOM
            body_text = cache.get("_dom_text", "") if cache else ""
            if not body_text:
                try:
                    body_text = await page.evaluate("() => document.body?.innerText || ''")
                except Exception:
                    body_text = ""

            # Extraer delivery time del texto visible
            if not store_data["estimated_delivery_time"] and body_text:
                time_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*min", body_text)
                if time_match:
                    store_data["estimated_delivery_time"] = f"{time_match.group(1)}-{time_match.group(2)} min"

            # Extraer rating del texto visible
            if not store_data["rating"] and body_text:
                rating_match = re.search(r"(\d\.\d)\s*(?:★|⭐|estrellas|rating)", body_text, re.IGNORECASE)
                if rating_match:
                    store_data["rating"] = float(rating_match.group(1))

            # Buscar productos
            for product in products:
                product_data = self._find_product_in_data(product, body_text)
                store_data["products"].append(product_data)

        except Exception as e:
            log.error(f"Error scrapeando restaurante {restaurant_name}: {e}")

        self._store_data_cache = {}
        return store_data

    def _find_product_in_data(self, product: dict, body_text: str) -> dict:
        """Busca un producto en los datos capturados (API + DOM)."""
        product_data = {
            "product_id": product["id"],
            "product_name": product["name"],
            "found": False,
            "price": None,
            "original_price": None,
            "discount": None,
            "available": False,
        }

        # Buscar en APIs capturadas
        for api_resp in self._api_responses:
            data = api_resp.get("data")
            if not data:
                continue
            data_str = json.dumps(data, ensure_ascii=False).lower()
            for search_term in product["search_terms"]:
                if search_term.lower() in data_str:
                    # Buscar precio cerca del nombre del producto
                    prices = self._extract_prices_near_product(data, search_term)
                    if prices:
                        product_data["found"] = True
                        product_data["available"] = True
                        product_data["price"] = prices[0]
                        if len(prices) > 1 and prices[1] > prices[0]:
                            product_data["original_price"] = prices[1]
                            product_data["discount"] = round((1 - prices[0] / prices[1]) * 100, 1)
                        return product_data

        # Buscar en texto del DOM
        for search_term in product["search_terms"]:
            if search_term.lower() in body_text.lower():
                idx = body_text.lower().index(search_term.lower())
                context = body_text[max(0, idx - 50):idx + 200]
                prices = re.findall(r"\$\s*([\d,]+(?:\.\d{2})?)", context)
                if prices:
                    product_data["found"] = True
                    product_data["available"] = True
                    product_data["price"] = float(prices[0].replace(",", ""))
                    if len(prices) > 1:
                        p2 = float(prices[1].replace(",", ""))
                        if p2 > product_data["price"]:
                            product_data["original_price"] = p2
                            product_data["discount"] = round((1 - product_data["price"] / p2) * 100, 1)
                    return product_data

        return product_data

    def _extract_prices_near_product(self, data: any, search_term: str) -> list[float]:
        """Extrae precios de una estructura JSON cerca de un producto."""
        prices = []
        try:
            data_str = json.dumps(data, ensure_ascii=False)
            # Buscar el producto y extraer precios cercanos
            pattern = rf'(?i){re.escape(search_term)}[^{{}}]*?"(?:price|precio|real_price|unit_price)":\s*(\d+(?:\.\d+)?)'
            matches = re.findall(pattern, data_str)
            for m in matches:
                prices.append(float(m))

            if not prices:
                # Buscar pattern alternativo
                pattern2 = rf'"(?:price|precio|real_price)":\s*(\d+(?:\.\d+)?)[^{{}}]*?(?i){re.escape(search_term)}'
                matches2 = re.findall(pattern2, data_str)
                for m in matches2:
                    prices.append(float(m))
        except Exception:
            pass
        return prices

    async def scrape_fees(self, page: Page) -> dict:
        """Extrae delivery fee y service fee de Rappi (API + DOM)."""
        fees = {
            "delivery_fee": None,
            "service_fee": None,
            "small_order_fee": None,
            "free_delivery": False,
        }

        try:
            # Buscar en APIs capturadas
            for api_resp in self._api_responses:
                data_str = json.dumps(api_resp.get("data", {}), ensure_ascii=False).lower()
                fee_patterns = [
                    (r'"delivery_fee":\s*(\d+(?:\.\d+)?)', "delivery_fee"),
                    (r'"shipping_fee":\s*(\d+(?:\.\d+)?)', "delivery_fee"),
                    (r'"service_fee":\s*(\d+(?:\.\d+)?)', "service_fee"),
                ]
                for pattern, fee_key in fee_patterns:
                    match = re.search(pattern, data_str)
                    if match:
                        fees[fee_key] = float(match.group(1))

            # Complementar con DOM
            try:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
            except Exception:
                body_text = ""

            if body_text:
                if fees["delivery_fee"] is None:
                    match = re.search(r"[Ee]nvío[:\s]*\$\s*([\d,]+(?:\.\d{2})?)", body_text)
                    if match:
                        fees["delivery_fee"] = float(match.group(1).replace(",", ""))

                if re.search(r"[Ee]nvío\s+[Gg]ratis|[Gg]ratis", body_text):
                    fees["free_delivery"] = True
                    if fees["delivery_fee"] is None:
                        fees["delivery_fee"] = 0.0

                if fees["service_fee"] is None:
                    match = re.search(r"[Ss]ervicio[:\s]*\$\s*([\d,]+(?:\.\d{2})?)", body_text)
                    if match:
                        fees["service_fee"] = float(match.group(1).replace(",", ""))

        except Exception as e:
            log.debug(f"Error extrayendo fees de Rappi: {e}")

        return fees

    async def scrape_promotions(self, page: Page) -> list[dict]:
        """Extrae promociones visibles en Rappi (API + DOM)."""
        promotions = []

        try:
            # Buscar en APIs capturadas
            for api_resp in self._api_responses:
                data_str = json.dumps(api_resp.get("data", {}), ensure_ascii=False)
                promo_patterns = [
                    r'"(?:promo_text|promotion_text|discount_text|banner_text)":\s*"([^"]{5,200})"',
                    r'"(?:description|title)":\s*"([^"]*(?:descuento|gratis|off|2x1|promo)[^"]*)"',
                ]
                for pattern in promo_patterns:
                    matches = re.findall(pattern, data_str, re.IGNORECASE)
                    for m in matches[:5]:
                        promotions.append({
                            "platform": self.PLATFORM_NAME,
                            "type": "promotion",
                            "description": m.strip()[:200],
                        })

            # Buscar en DOM
            try:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
            except Exception:
                body_text = ""

            if body_text:
                patterns = [
                    r"(\d+%\s*(?:de\s+)?(?:desc|off|descuento)[^\n]{0,50})",
                    r"(2x1[^\n]{0,50})",
                    r"([Ee]nvío\s+[Gg]ratis[^\n]{0,50})",
                    r"(\$\d+\s+de\s+descuento[^\n]{0,50})",
                    r"([Gg]ratis[^\n]{0,30})",
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, body_text)
                    for m in matches[:3]:
                        promotions.append({
                            "platform": self.PLATFORM_NAME,
                            "type": "discount",
                            "description": m.strip()[:200],
                        })

        except Exception as e:
            log.debug(f"Error extrayendo promociones de Rappi: {e}")

        seen = set()
        unique = []
        for p in promotions:
            if p["description"] not in seen:
                seen.add(p["description"])
                unique.append(p)

        return unique[:20]
