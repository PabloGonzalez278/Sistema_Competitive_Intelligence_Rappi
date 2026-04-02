"""
Scraper base con lógica compartida: navegación, reintentos, anti-detección,
manejo de errores, screenshots y persistencia de datos.
"""
import json
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config.settings import (
    HEADLESS, TIMEOUT, MAX_RETRIES, RETRY_DELAY,
    DATA_DIR, SCREENSHOTS_DIR, TIMESTAMP_FORMAT,
)
from utils.anti_detection import (
    get_browser_context_options,
    get_proxy_config,
    get_stealth_scripts,
    random_delay,
    detect_block,
)
from utils.logger import get_logger


class ScrapingResult:
    """Resultado estructurado de una operación de scraping."""

    def __init__(self, platform: str, address: dict, timestamp: str):
        self.platform = platform
        self.address_id = address["id"]
        self.address_name = address["name"]
        self.address_full = address["address"]
        self.zone_type = address["zone_type"]
        self.lat = address["lat"]
        self.lng = address["lng"]
        self.timestamp = timestamp
        self.restaurants: list[dict] = []
        self.products: list[dict] = []
        self.fees: dict = {}
        self.promotions: list[dict] = []
        self.errors: list[str] = []
        self.metadata: dict = {}

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "address_id": self.address_id,
            "address_name": self.address_name,
            "address_full": self.address_full,
            "zone_type": self.zone_type,
            "coordinates": {"lat": self.lat, "lng": self.lng},
            "timestamp": self.timestamp,
            "restaurants": self.restaurants,
            "products": self.products,
            "fees": self.fees,
            "promotions": self.promotions,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class BaseScraper(ABC):
    """Clase base abstracta para todos los scrapers de plataformas."""

    PLATFORM_NAME: str = ""
    BASE_URL: str = ""

    def __init__(self):
        self.log = get_logger(f"scraper.{self.PLATFORM_NAME}")
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.results: list[ScrapingResult] = []
        self._blocked = False

    async def init_browser(self) -> None:
        self.log.info(f"Inicializando navegador para {self.PLATFORM_NAME}")
        self._playwright = await async_playwright().start()

        launch_opts: dict[str, Any] = {
            "headless": HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        proxy = get_proxy_config()
        if proxy:
            launch_opts["proxy"] = proxy

        self.browser = await self._playwright.chromium.launch(**launch_opts)
        ctx_opts = get_browser_context_options()
        self.context = await self.browser.new_context(**ctx_opts)
        self.context.set_default_timeout(TIMEOUT)

        # Inyectar scripts de stealth en cada nueva página
        await self.context.add_init_script(get_stealth_scripts())

    async def close_browser(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.log.info(f"Navegador cerrado para {self.PLATFORM_NAME}")

    async def new_page(self) -> Page:
        if not self.context:
            await self.init_browser()
        page = await self.context.new_page()
        # Solo bloquear videos y fonts pesados (NO imágenes — bloquearlas delata al bot)
        await page.route("**/*.{woff,woff2,mp4,webm}", lambda route: route.abort())
        return page

    async def safe_goto(self, page: Page, url: str, retries: int = MAX_RETRIES) -> bool:
        for attempt in range(1, retries + 1):
            try:
                self.log.debug(f"Navegando a {url} (intento {attempt}/{retries})")
                response = await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
                if response and response.status in (403, 429):
                    self.log.warning(f"HTTP {response.status} en {url}")
                    if attempt < retries:
                        await asyncio.sleep(RETRY_DELAY * attempt)
                        continue
                    return False

                if await detect_block(page):
                    self._blocked = True
                    if attempt < retries:
                        self.log.warning(f"Bloqueo detectado, reintentando en {RETRY_DELAY * attempt}s...")
                        await asyncio.sleep(RETRY_DELAY * attempt)
                        continue
                    return False

                return True
            except Exception as e:
                self.log.error(f"Error navegando a {url}: {e}")
                if attempt < retries:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return False
        return False

    async def take_screenshot(self, page: Page, name: str) -> str | None:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = SCREENSHOTS_DIR / f"{self.PLATFORM_NAME}_{name}_{ts}.png"
            await page.screenshot(path=str(path), full_page=False)
            self.log.debug(f"Screenshot guardado: {path}")
            return str(path)
        except Exception as e:
            self.log.error(f"Error tomando screenshot: {e}")
            return None

    @abstractmethod
    async def set_location(self, page: Page, address: dict) -> bool:
        """Configura la ubicación/dirección en la plataforma."""
        ...

    @abstractmethod
    async def scrape_restaurant(self, page: Page, restaurant_name: str, products: list[dict]) -> dict:
        """Scrapea datos de un restaurante específico."""
        ...

    @abstractmethod
    async def scrape_fees(self, page: Page) -> dict:
        """Extrae fees (delivery fee, service fee) de la página actual."""
        ...

    @abstractmethod
    async def scrape_promotions(self, page: Page) -> list[dict]:
        """Extrae promociones y descuentos visibles."""
        ...

    @abstractmethod
    async def search_store(self, page: Page, store_name: str) -> bool:
        """Busca una tienda/restaurante en la plataforma."""
        ...

    async def scrape_address(self, address: dict, products_config: dict) -> ScrapingResult:
        """Ejecuta scraping completo para una dirección."""
        timestamp = datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)
        result = ScrapingResult(self.PLATFORM_NAME, address, timestamp)

        page = await self.new_page()
        try:
            # Navegar a la plataforma
            if not await self.safe_goto(page, self.BASE_URL):
                result.errors.append("No se pudo acceder a la plataforma")
                return result

            # Configurar ubicación
            if not await self.set_location(page, address):
                result.errors.append(f"No se pudo configurar la ubicación: {address['address']}")
                return result

            await random_delay()

            # Scrapear cada categoría de productos
            for cat_key, category in products_config["categories"].items():
                store_name = category.get("restaurant") or category.get("store", "")
                if not store_name:
                    continue

                self.log.info(f"  Buscando {store_name} en {address['name']}...")

                if not await self.search_store(page, store_name):
                    result.errors.append(f"Tienda no encontrada: {store_name}")
                    await random_delay()
                    continue

                await random_delay(0.5)

                # Scrape productos
                store_data = await self.scrape_restaurant(page, store_name, category["products"])
                if store_data:
                    result.products.append(store_data)

                # Scrape fees
                fees = await self.scrape_fees(page)
                if fees:
                    result.fees[store_name] = fees

                # Scrape promociones
                promos = await self.scrape_promotions(page)
                if promos:
                    result.promotions.extend(promos)

                # Screenshot como evidencia
                await self.take_screenshot(page, f"{address['id']}_{store_name.replace(' ', '_')}")

                await random_delay()

            result.metadata["scraping_completed"] = True
            result.metadata["blocked"] = self._blocked

        except Exception as e:
            self.log.error(f"Error scrapeando {address['name']}: {e}")
            result.errors.append(str(e))
        finally:
            await page.close()

        self.results.append(result)
        return result

    async def run(self, addresses: list[dict], products_config: dict) -> list[dict]:
        """Ejecuta el scraping para todas las direcciones."""
        self.log.info(f"=== Iniciando scraping de {self.PLATFORM_NAME} ===")
        self.log.info(f"Direcciones a procesar: {len(addresses)}")

        await self.init_browser()
        all_results = []

        try:
            for i, address in enumerate(addresses, 1):
                self.log.info(f"[{i}/{len(addresses)}] Procesando: {address['name']} ({address['zone_type']})")
                result = await self.scrape_address(address, products_config)
                all_results.append(result.to_dict())

                # Delay entre direcciones
                if i < len(addresses):
                    await random_delay(1.5)

        finally:
            await self.close_browser()

        # Guardar resultados
        self._save_results(all_results)
        self.log.info(f"=== Scraping de {self.PLATFORM_NAME} completado: {len(all_results)} direcciones ===")
        return all_results

    def _save_results(self, results: list[dict]) -> None:
        ts = datetime.now().strftime(TIMESTAMP_FORMAT)
        output_path = DATA_DIR / f"{self.PLATFORM_NAME}_{ts}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        self.log.info(f"Resultados guardados en: {output_path}")
