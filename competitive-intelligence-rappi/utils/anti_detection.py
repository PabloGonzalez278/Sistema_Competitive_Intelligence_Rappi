"""
Estrategias anti-detección para scraping ético y responsable.
Fase 1: Técnicas básicas sin proxy + stealth mode.
Fase 2: Integración con ScraperAPI si se detectan bloqueos reales.
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


# JavaScript para inyectar en cada página y evadir detección de bots
STEALTH_SCRIPTS = """
// Overwrite navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Overwrite chrome runtime
window.chrome = { runtime: {} };

// Overwrite permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);

// Overwrite plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Overwrite languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['es-MX', 'es', 'en-US', 'en'],
});

// Remove automation indicators
delete window.__nightmare;
delete window._phantom;
delete window.callPhantom;
delete window._selenium;
delete window.domAutomation;
delete window.domAutomationController;
"""


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
            "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    }


def get_stealth_scripts() -> str:
    """Retorna los scripts de stealth para inyectar en el browser context."""
    return STEALTH_SCRIPTS


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
    """
    Detecta si la página está REALMENTE bloqueada.

    IMPORTANTE: No buscar 'captcha' en el HTML completo porque casi todos los
    sitios modernos cargan scripts de reCAPTCHA/hCaptcha de forma preventiva
    sin estar bloqueando al usuario. Solo detectamos bloqueo REAL.
    """
    try:
        # 1. Verificar si hay un CAPTCHA VISIBLE en pantalla (no solo en el source)
        captcha_visible = await page.evaluate("""
            () => {
                // Buscar iframes de captcha visibles
                const captchaFrames = document.querySelectorAll(
                    'iframe[src*="recaptcha"][style*="visible"], ' +
                    'iframe[src*="hcaptcha"][style*="visible"], ' +
                    'iframe[src*="captcha"]:not([style*="display: none"]):not([style*="visibility: hidden"])'
                );
                for (const frame of captchaFrames) {
                    const rect = frame.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 50) return true;
                }

                // Buscar divs de captcha visibles con tamaño significativo
                const captchaDivs = document.querySelectorAll(
                    '.g-recaptcha:not([style*="display: none"]), ' +
                    '.h-captcha:not([style*="display: none"]), ' +
                    '[class*="captcha-container"]:not([style*="display: none"])'
                );
                for (const div of captchaDivs) {
                    const rect = div.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 50) return true;
                }

                return false;
            }
        """)

        if captcha_visible:
            log.warning("CAPTCHA visible detectado en la página")
            return True

        # 2. Verificar si la página está en blanco o muestra error de acceso
        body_text = await page.evaluate("""
            () => {
                const body = document.body;
                if (!body) return '';
                return body.innerText.substring(0, 2000).toLowerCase();
            }
        """)

        # Solo señales de bloqueo REALES en texto visible
        hard_block_signals = [
            "access denied",
            "403 forbidden",
            "you have been blocked",
            "your access to this site has been limited",
            "too many requests",
            "rate limit exceeded",
            "please complete the security check",
            "verify you are human",
            "we need to verify that you're not a robot",
        ]

        for signal in hard_block_signals:
            if signal in body_text:
                log.warning(f"Bloqueo real detectado: '{signal}'")
                return True

        # 3. Verificar si la página está vacía (posible bloqueo silencioso)
        if len(body_text.strip()) < 20:
            # Página casi vacía — podría ser un bloqueo o una carga lenta
            log.debug("Página con poco contenido, posible carga lenta")
            return False  # No asumir bloqueo, dejar que continúe

        return False

    except Exception as e:
        log.debug(f"Error verificando bloqueo: {e}")
        return False
