"""
Configuración central del sistema de Competitive Intelligence.
"""
import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data" / "raw"
REPORTS_DIR = BASE_DIR / "reports"
SCREENSHOTS_DIR = BASE_DIR / "data" / "screenshots"

# Crear directorios si no existen
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Scraping ---
REQUEST_DELAY_MIN = 2  # segundos mínimo entre requests
REQUEST_DELAY_MAX = 5  # segundos máximo entre requests
MAX_RETRIES = 3
RETRY_DELAY = 10  # segundos entre reintentos
TIMEOUT = 30000  # ms para Playwright
HEADLESS = True  # Ejecutar navegador sin interfaz

# --- Proxy (ScraperAPI) ---
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")
USE_PROXY = os.environ.get("USE_PROXY", "false").lower() == "true"
SCRAPER_API_URL = "http://api.scraperapi.com"

# --- User Agents (rotación) ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]

# --- Plataformas ---
PLATFORMS = {
    "rappi": {
        "base_url": "https://www.rappi.com.mx",
        "name": "Rappi",
        "country_code": "mx"
    },
    "uber_eats": {
        "base_url": "https://www.ubereats.com/mx",
        "name": "Uber Eats",
        "country_code": "mx"
    },
    "didi_food": {
        "base_url": "https://www.didi-food.com/es-MX",
        "name": "DiDi Food",
        "country_code": "mx"
    }
}

# --- Output ---
OUTPUT_FORMAT = "json"  # json o csv
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "logs" / "scraper.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
