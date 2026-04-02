"""
Scraper para DiDi Food México.
Estrategia: Intercepta las APIs internas + extrae datos del DOM.
"""
import re
import json
import asyncio
from playwright.async_api import Page, Response

from scrapers.base_scraper import BaseScraper
from utils.anti_detection import random_delay
from utils.logger import get_logger

log = get_logger("scraper.didi_food")


class DidiFoodScraper(BaseScraper):
    PLATFORM_NAME = "didi_food"
    BASE_URL = "https://www.didi-food.com/es-MX"

    def __init__(self):
        super().__init__()
        self._api_responses: list[dict] = []
        self._store_data_cache: dict = {}

    async def _capture_api_responses(self, response: Response) -> None:
        """Captura respuestas API del backend de DiDi Food."""
        try:
            url = response.url
            if response.status == 200 and ("api" in url or "didi" in url or "food" in url):
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    try:
                        body = await response.json()
                        self._api_responses.append({"url": url, "data": body})
                    except Exception:
                        pass
        except Exception:
            pass

    async def set_location(self, page: Page, address: dict) -> bool:
        """Configura la ubicación en DiDi Food."""
        try:
            self._api_responses = []
            page.on("response", self._capture_api_responses)

            lat, lng = address["lat"], address["lng"]
            url = f"{self.BASE_URL}/restaurant/listing?lat={lat}&lng={lng}"
            if not await self.safe_goto(page, url):
                # Fallback URL base
                if not await self.safe_goto(page, self.BASE_URL):
                    return False

            await page.wait_for_load_state("networkidle", timeout=20000)
            await asyncio.sleep(3)

            log.info(f"Ubicación configurada en DiDi Food: {address['name']} (APIs: {len(self._api_responses)})")
            return True

        except Exception as e:
            log.error(f"Error configurando ubicación en DiDi Food: {e}")
            return True

    async def search_store(self, page: Page, store_name: str) -> bool:
        """Busca un restaurante en DiDi Food."""
        try:
            self._api_responses = []
            self._store_data_cache = {}
            search_term = store_name.split("/")[0].strip()

            # Navegar a búsqueda
            search_url = f"{self.BASE_URL}/search?keyword={search_term.replace(' ', '%20')}"
            await self.safe_goto(page, search_url)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(3)

            # Buscar en APIs
            self._extract_store_from_apis(search_term)

            if self._store_data_cache:
                log.info(f"Datos de {store_name} capturados via API en DiDi Food")

            # Intentar clic en resultado
            try:
                store_link = page.locator('a[href*="/restaurant/"]').first
                if await store_link.is_visible(timeout=5000):
                    await store_link.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    return True
            except Exception:
                pass

            # DOM fallback
            body_text = await page.evaluate("() => document.body?.innerText || ''")
            if search_term.lower() in body_text.lower():
                self._store_data_cache["_dom_text"] = body_text
                return True

            if self._store_data_cache:
                return True

            log.warning(f"No se encontró {store_name} en DiDi Food")
            return False

        except Exception as e:
            log.error(f"Error buscando {store_name} en DiDi Food: {e}")
            return False

    def _extract_store_from_apis(self, search_term: str) -> None:
        """Extrae datos de tienda de las APIs capturadas."""
        search_lower = search_term.lower()
        for api_resp in self._api_responses:
            data = api_resp.get("data")
            if not data:
                continue
            data_str = json.dumps(data, ensure_ascii=False).lower()
            if search_lower in data_str:
                if isinstance(data, dict):
                    self._store_data_cache = data
                    return

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
            try:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
            except Exception:
                body_text = self._store_data_cache.get("_dom_text", "")

            # Delivery time
            time_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*min", body_text)
            if time_match:
                store_data["estimated_delivery_time"] = f"{time_match.group(1)}-{time_match.group(2)} min"

            # Rating
            rating_match = re.search(r"(\d\.\d)\s*(?:\(|★|⭐|estrellas)", body_text)
            if rating_match:
                store_data["rating"] = float(rating_match.group(1))

            # APIs
            for api_resp in self._api_responses:
                data_str = json.dumps(api_resp.get("data", {}), ensure_ascii=False)
                if not store_data["estimated_delivery_time"]:
                    m = re.search(r'"(?:delivery_time|eta|estimatedDelivery)":\s*"?(\d+)', data_str)
                    if m:
                        store_data["estimated_delivery_time"] = f"{m.group(1)} min"
                if not store_data["rating"]:
                    m = re.search(r'"(?:rating|score|shop_score)":\s*(\d+\.?\d*)', data_str)
                    if m:
                        val = float(m.group(1))
                        if val <= 5:
                            store_data["rating"] = val

            for product in products:
                product_data = self._find_product(product, body_text)
                store_data["products"].append(product_data)

        except Exception as e:
            log.error(f"Error scrapeando {restaurant_name} en DiDi Food: {e}")

        self._store_data_cache = {}
        return store_data

    def _find_product(self, product: dict, body_text: str) -> dict:
        """Busca un producto en APIs + DOM."""
        product_data = {
            "product_id": product["id"],
            "product_name": product["name"],
            "found": False,
            "price": None,
            "original_price": None,
            "discount": None,
            "available": False,
        }

        # APIs
        for api_resp in self._api_responses:
            data_str = json.dumps(api_resp.get("data", {}), ensure_ascii=False)
            for search_term in product["search_terms"]:
                if search_term.lower() in data_str.lower():
                    patterns = [
                        rf'(?i){re.escape(search_term)}[^{{}}]*?"(?:price|dish_price|unit_price)":\s*(\d+(?:\.\d+)?)',
                        rf'"(?:price|dish_price)":\s*(\d+(?:\.\d+)?)[^{{}}]*?(?i){re.escape(search_term)}',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, data_str)
                        if match:
                            price = float(match.group(1))
                            if price > 10000:
                                price = price / 100
                            product_data.update({"found": True, "available": True, "price": round(price, 2)})
                            return product_data

        # DOM
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

    async def scrape_fees(self, page: Page) -> dict:
        """Extrae fees de DiDi Food."""
        fees = {"delivery_fee": None, "service_fee": None, "small_order_fee": None, "free_delivery": False}

        try:
            for api_resp in self._api_responses:
                data_str = json.dumps(api_resp.get("data", {}), ensure_ascii=False).lower()
                for pattern, key in [
                    (r'"delivery_fee":\s*(\d+(?:\.\d+)?)', "delivery_fee"),
                    (r'"shipping_fee":\s*(\d+(?:\.\d+)?)', "delivery_fee"),
                    (r'"service_fee":\s*(\d+(?:\.\d+)?)', "service_fee"),
                ]:
                    match = re.search(pattern, data_str)
                    if match and fees[key] is None:
                        val = float(match.group(1))
                        if val > 10000:
                            val = val / 100
                        fees[key] = round(val, 2)

            try:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
            except Exception:
                body_text = ""

            if body_text:
                if fees["delivery_fee"] is None:
                    m = re.search(r"(?:Envío|Entrega|Delivery)[:\s]*\$\s*([\d,.]+)", body_text, re.IGNORECASE)
                    if m:
                        fees["delivery_fee"] = float(m.group(1).replace(",", ""))

                if re.search(r"Envío\s+Gratis|Entrega\s+Gratis|Free Delivery|\$0\s*envío", body_text, re.IGNORECASE):
                    fees["free_delivery"] = True
                    if fees["delivery_fee"] is None:
                        fees["delivery_fee"] = 0.0

        except Exception as e:
            log.debug(f"Error extrayendo fees de DiDi Food: {e}")

        return fees

    async def scrape_promotions(self, page: Page) -> list[dict]:
        """Extrae promociones de DiDi Food."""
        promotions = []

        try:
            for api_resp in self._api_responses:
                data_str = json.dumps(api_resp.get("data", {}), ensure_ascii=False)
                patterns = [
                    r'"(?:promo_text|discount_text|promotion_text|badge_text)":\s*"([^"]{5,200})"',
                    r'"(?:text|title|name)":\s*"([^"]*(?:descuento|gratis|off|2x1|cupón|promo)[^"]*)"',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, data_str, re.IGNORECASE)
                    for m in matches[:5]:
                        promotions.append({"platform": self.PLATFORM_NAME, "type": "promotion", "description": m.strip()[:200]})

            try:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
            except Exception:
                body_text = ""

            if body_text:
                for pattern in [
                    r"(\d+%\s*(?:de\s+)?(?:desc|off|descuento)[^\n]{0,50})",
                    r"(2x1[^\n]{0,50})",
                    r"([Ee]nvío\s+[Gg]ratis[^\n]{0,50})",
                    r"(\$\d+\s+de\s+descuento[^\n]{0,50})",
                ]:
                    matches = re.findall(pattern, body_text, re.IGNORECASE)
                    for m in matches[:3]:
                        promotions.append({"platform": self.PLATFORM_NAME, "type": "discount", "description": m.strip()[:200]})

        except Exception as e:
            log.debug(f"Error extrayendo promociones de DiDi Food: {e}")

        seen = set()
        unique = []
        for p in promotions:
            if p["description"] not in seen:
                seen.add(p["description"])
                unique.append(p)
        return unique[:20]
