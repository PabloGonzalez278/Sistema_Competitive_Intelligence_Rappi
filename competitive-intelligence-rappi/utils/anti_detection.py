"""
Estrategias anti-detección para scraping ético y responsable.
Fase 1: Técnicas básicas sin proxy.
Fase 2: Integración con ScraperAPI si se detectan bloqueos.
"""
import random
import asyncio
from config.settings import (
    USER_AGENTS,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    SCRAPER_API_KEY,
    USE_PROXY,
)
from utils.logger import get_logger

log = get_logger("anti_detection")


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


async def random_delay(multiplier: float = 1.0) -> None:
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX) * multiplier
    log.debug(f"Esperando {delay:.1f}s antes de siguiente request")
    await asyncio.sleep(delay)


def get_browser_context_options() -> dict:
    ua = get_random_user_agent()
    return {
        "user_agent": ua,
        "viewport": {"width": random.choice([1366, 1440, 1536, 1920]), "height": random.choice([768, 900, 1080])},
        "locale": "es-MX",
        "timezone_id": "America/Mexico_City",
        "geolocation": None,
        "permissions": [],
        "extra_http_headers": {
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        },
    }


def get_proxy_config() -> dict | None:
    if not USE_PROXY or not SCRAPER_API_KEY:
        return None
    log.info("Usando ScraperAPI como proxy")
    return {
        "server": f"http://proxy-server.scraperapi.com:8001",
        "username": "scraperapi",
        "password": SCRAPER_API_KEY,
    }


def build_scraper_api_url(target_url: str) -> str:
    if not SCRAPER_API_KEY:
        return target_url
    return f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={target_url}&country_code=mx"


async def detect_block(page) -> bool:
    """Detecta si la página muestra señales de bloqueo."""
    try:
        content = await page.content()
        block_signals = [
            "captcha", "CAPTCHA", "robot", "blocked", "access denied",
            "rate limit", "too many requests", "403 Forbidden",
            "Please verify", "unusual traffic",
        ]
        for signal in block_signals:
            if signal.lower() in content.lower():
                log.warning(f"Señal de bloqueo detectada: '{signal}'")
                return True
        return False
    except Exception:
        return False
