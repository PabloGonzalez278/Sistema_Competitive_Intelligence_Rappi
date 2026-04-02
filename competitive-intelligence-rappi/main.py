"""
Sistema de Competitive Intelligence para Rappi
===============================================
Orquestador principal que ejecuta scrapers de Rappi, Uber Eats y DiDi Food,
y genera un informe analítico con insights accionables.

Uso:
    python main.py                          # Ejecutar scraping completo
    python main.py --platforms rappi uber    # Solo plataformas específicas
    python main.py --addresses 5            # Limitar a N direcciones
    python main.py --analyze-only           # Solo generar análisis con datos existentes
    python main.py --report                 # Generar informe HTML
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import DATA_DIR, CONFIG_DIR, TIMESTAMP_FORMAT
from scrapers.rappi_scraper import RappiScraper
from scrapers.ubereats_scraper import UberEatsScraper
from scrapers.didifood_scraper import DidiFoodScraper
from analysis.analyzer import CompetitiveAnalyzer
from analysis.visualizations import generate_report
from utils.logger import get_logger

log = get_logger("main")

SCRAPERS = {
    "rappi": RappiScraper,
    "uber_eats": UberEatsScraper,
    "didi_food": DidiFoodScraper,
}


def load_config() -> tuple[list[dict], dict]:
    """Carga configuración de direcciones y productos."""
    with open(CONFIG_DIR / "addresses.json", "r", encoding="utf-8") as f:
        addresses_data = json.load(f)

    with open(CONFIG_DIR / "products.json", "r", encoding="utf-8") as f:
        products_data = json.load(f)

    return addresses_data["addresses"], products_data


async def run_scraper(scraper_class, addresses: list[dict], products: dict) -> list[dict]:
    """Ejecuta un scraper individual."""
    scraper = scraper_class()
    try:
        results = await scraper.run(addresses, products)
        return results
    except Exception as e:
        log.error(f"Error ejecutando {scraper.PLATFORM_NAME}: {e}")
        return []


async def run_all_scrapers(
    platforms: list[str],
    addresses: list[dict],
    products: dict,
) -> dict[str, list[dict]]:
    """Ejecuta todos los scrapers secuencialmente (para evitar rate limiting simultáneo)."""
    all_results = {}

    for platform in platforms:
        if platform not in SCRAPERS:
            log.warning(f"Plataforma desconocida: {platform}")
            continue

        log.info(f"\n{'='*60}")
        log.info(f"  INICIANDO SCRAPING: {platform.upper()}")
        log.info(f"{'='*60}")

        results = await run_scraper(SCRAPERS[platform], addresses, products)
        all_results[platform] = results

        log.info(f"  {platform}: {len(results)} resultados obtenidos")

    return all_results


def save_combined_results(all_results: dict[str, list[dict]]) -> Path:
    """Guarda todos los resultados combinados en un solo archivo JSON."""
    ts = datetime.now().strftime(TIMESTAMP_FORMAT)
    output = {
        "metadata": {
            "timestamp": ts,
            "platforms": list(all_results.keys()),
            "total_records": sum(len(v) for v in all_results.values()),
        },
        "results": all_results,
    }

    output_path = DATA_DIR / f"combined_results_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"Resultados combinados guardados en: {output_path}")
    return output_path


def load_latest_results() -> dict | None:
    """Carga los resultados más recientes del directorio de datos."""
    json_files = sorted(DATA_DIR.glob("combined_results_*.json"), reverse=True)
    if not json_files:
        # Intentar cargar archivos individuales por plataforma
        individual_files = sorted(DATA_DIR.glob("*.json"), reverse=True)
        if not individual_files:
            return None

        combined = {}
        for f in individual_files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            # Inferir plataforma del nombre del archivo
            for platform in SCRAPERS:
                if platform in f.name:
                    combined[platform] = data
                    break
        return {"results": combined} if combined else None

    with open(json_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sistema de Competitive Intelligence para Rappi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--platforms", "-p",
        nargs="+",
        choices=list(SCRAPERS.keys()),
        default=list(SCRAPERS.keys()),
        help="Plataformas a scrapear (default: todas)",
    )
    parser.add_argument(
        "--addresses", "-a",
        type=int,
        default=None,
        help="Número máximo de direcciones a procesar",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Solo ejecutar análisis con datos existentes",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generar informe HTML",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Ejecutar navegador en modo headless (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Ejecutar navegador con interfaz visible",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    log.info("=" * 60)
    log.info("  COMPETITIVE INTELLIGENCE SYSTEM - RAPPI")
    log.info("=" * 60)
    log.info(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"  Plataformas: {', '.join(args.platforms)}")

    if args.no_headless:
        from config import settings
        settings.HEADLESS = False

    if args.analyze_only or args.report:
        log.info("  Modo: Solo análisis")
        data = load_latest_results()
        if not data:
            log.error("No se encontraron datos para analizar. Ejecuta el scraper primero.")
            sys.exit(1)
    else:
        # Cargar configuración
        addresses, products = load_config()

        if args.addresses:
            addresses = addresses[:args.addresses]
            log.info(f"  Direcciones limitadas a: {args.addresses}")

        log.info(f"  Total direcciones: {len(addresses)}")
        log.info("")

        # Ejecutar scrapers
        all_results = await run_all_scrapers(args.platforms, addresses, products)

        # Guardar resultados combinados
        output_path = save_combined_results(all_results)
        data = {"results": all_results}

    # Ejecutar análisis
    log.info("\n" + "=" * 60)
    log.info("  GENERANDO ANÁLISIS COMPETITIVO")
    log.info("=" * 60)

    analyzer = CompetitiveAnalyzer(data["results"])
    analysis = analyzer.run_full_analysis()

    # Guardar análisis
    ts = datetime.now().strftime(TIMESTAMP_FORMAT)
    analysis_path = DATA_DIR / f"analysis_{ts}.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    log.info(f"Análisis guardado en: {analysis_path}")

    # Generar informe
    report_path = generate_report(analysis, data["results"])
    log.info(f"Informe generado en: {report_path}")

    log.info("\n" + "=" * 60)
    log.info("  PROCESO COMPLETADO")
    log.info("=" * 60)

    # Imprimir resumen de insights
    if "top_insights" in analysis:
        log.info("\n  TOP 5 INSIGHTS:")
        for i, insight in enumerate(analysis["top_insights"][:5], 1):
            log.info(f"  {i}. {insight.get('finding', 'N/A')}")

    return analysis


if __name__ == "__main__":
    asyncio.run(main())
