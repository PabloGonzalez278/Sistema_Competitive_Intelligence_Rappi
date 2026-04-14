"""
Exporta datos del análisis competitivo a Excel (múltiples hojas) y CSV
para importación directa en Power BI.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config.settings import DATA_DIR, REPORTS_DIR, TIMESTAMP_FORMAT


def load_latest_data() -> tuple[dict, dict]:
    """Carga los datos combinados y análisis más recientes."""
    combined_files = sorted(DATA_DIR.glob("combined_results_*.json"), reverse=True)
    analysis_files = sorted(DATA_DIR.glob("analysis_*.json"), reverse=True)

    if not combined_files:
        raise FileNotFoundError("No se encontraron archivos de datos combinados en data/raw/")

    with open(combined_files[0], "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    analysis = {}
    if analysis_files:
        with open(analysis_files[0], "r", encoding="utf-8") as f:
            analysis = json.load(f)

    print(f"Datos cargados: {combined_files[0].name}")
    if analysis:
        print(f"Análisis cargado: {analysis_files[0].name}")
    return raw_data, analysis


def build_prices_df(raw_data: dict) -> pd.DataFrame:
    """Construye DataFrame de precios por producto, plataforma y zona."""
    rows = []
    for platform, records in raw_data.get("results", {}).items():
        for record in records:
            address = record.get("address_name", "")
            zone = record.get("zone_type", "")
            for store in record.get("products", []):
                store_name = store.get("store_name", "")
                delivery_time = store.get("estimated_delivery_time", "")
                rating = store.get("rating")
                for product in store.get("products", []):
                    rows.append({
                        "Plataforma": platform,
                        "Dirección": address,
                        "Zona": zone,
                        "Tienda": store_name,
                        "Producto": product.get("product_name", ""),
                        "Product_ID": product.get("product_id", ""),
                        "Precio": product.get("price"),
                        "Precio_Original": product.get("original_price"),
                        "Descuento_%": product.get("discount"),
                        "Encontrado": product.get("found", False),
                        "Disponible": product.get("available", False),
                        "Tiempo_Entrega": delivery_time,
                        "Rating": rating,
                    })
    return pd.DataFrame(rows)


def build_fees_df(raw_data: dict) -> pd.DataFrame:
    """Construye DataFrame de fees por plataforma y dirección."""
    rows = []
    for platform, records in raw_data.get("results", {}).items():
        for record in records:
            address = record.get("address_name", "")
            zone = record.get("zone_type", "")
            for store_name, fees in record.get("fees", {}).items():
                rows.append({
                    "Plataforma": platform,
                    "Dirección": address,
                    "Zona": zone,
                    "Tienda": store_name,
                    "Delivery_Fee": fees.get("delivery_fee"),
                    "Service_Fee": fees.get("service_fee"),
                    "Small_Order_Fee": fees.get("small_order_fee"),
                    "Envío_Gratis": fees.get("free_delivery", False),
                })
    return pd.DataFrame(rows)


def build_promotions_df(raw_data: dict) -> pd.DataFrame:
    """Construye DataFrame de promociones."""
    rows = []
    for platform, records in raw_data.get("results", {}).items():
        for record in records:
            address = record.get("address_name", "")
            zone = record.get("zone_type", "")
            for promo in record.get("promotions", []):
                rows.append({
                    "Plataforma": platform,
                    "Dirección": address,
                    "Zona": zone,
                    "Tipo": promo.get("type", ""),
                    "Descripción": promo.get("description", ""),
                })
    return pd.DataFrame(rows)


def build_summary_df(analysis: dict) -> pd.DataFrame:
    """Construye DataFrame resumen por plataforma."""
    rows = []
    fee_comp = analysis.get("fee_comparison", {})
    delivery_comp = analysis.get("delivery_time_comparison", {})
    avail = analysis.get("availability_analysis", {})
    promo = analysis.get("promotion_analysis", {})

    for platform in ["rappi", "uber_eats", "didi_food"]:
        row = {"Plataforma": platform}
        # Fees
        fees = fee_comp.get(platform, {})
        row["Delivery_Fee_Promedio"] = fees.get("delivery_fee", {}).get("avg")
        row["Service_Fee_Promedio"] = fees.get("service_fee", {}).get("avg")
        row["Envío_Gratis_%"] = fees.get("delivery_fee", {}).get("free_delivery_pct")
        # Delivery time
        dt = delivery_comp.get(platform, {})
        row["Tiempo_Entrega_Promedio"] = dt.get("avg_minutes")
        row["Tiempo_Entrega_Min"] = dt.get("min_minutes")
        row["Tiempo_Entrega_Max"] = dt.get("max_minutes")
        # Availability
        av = avail.get(platform, {})
        row["Tiendas_Encontradas"] = av.get("stores_found", 0)
        row["Tasa_Disponibilidad_Tiendas_%"] = av.get("store_availability_rate", 0)
        row["Tasa_Disponibilidad_Productos_%"] = av.get("product_availability_rate", 0)
        # Promotions
        pr = promo.get(platform, {})
        row["Total_Promociones"] = pr.get("total_promotions", 0)
        row["Promociones_Únicas"] = pr.get("unique_promotions", 0)

        rows.append(row)
    return pd.DataFrame(rows)


def build_geographic_df(analysis: dict) -> pd.DataFrame:
    """Construye DataFrame de análisis geográfico."""
    rows = []
    geo = analysis.get("geographic_analysis", {})
    for zone, platforms in geo.items():
        for platform, data in platforms.items():
            rows.append({
                "Zona": zone,
                "Plataforma": platform,
                "Precio_Promedio": data.get("avg_price"),
                "Delivery_Fee_Promedio": data.get("avg_delivery_fee"),
                "Tiempo_Entrega_Promedio": data.get("avg_delivery_time"),
                "Data_Points": data.get("data_points", 0),
            })
    return pd.DataFrame(rows)


def build_insights_df(analysis: dict) -> pd.DataFrame:
    """Construye DataFrame de Top 5 Insights."""
    rows = []
    for insight in analysis.get("top_insights", []):
        rows.append({
            "ID": insight.get("id"),
            "Categoría": insight.get("category", ""),
            "Finding": insight.get("finding", ""),
            "Impacto": insight.get("impact", ""),
            "Recomendación": insight.get("recommendation", ""),
        })
    return pd.DataFrame(rows)


def export_to_excel(dfs: dict[str, pd.DataFrame], output_path: Path) -> None:
    """Exporta múltiples DataFrames a un archivo Excel con hojas separadas."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print(f"Excel generado: {output_path}")


def export_to_csv(dfs: dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Exporta cada DataFrame a un archivo CSV individual."""
    csv_dir = output_dir / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for name, df in dfs.items():
        csv_path = csv_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"CSV generado: {csv_path}")


def main():
    raw_data, analysis = load_latest_data()

    # Build DataFrames
    prices_df = build_prices_df(raw_data)
    fees_df = build_fees_df(raw_data)
    promos_df = build_promotions_df(raw_data)
    geo_df = build_geographic_df(analysis)
    summary_df = build_summary_df(analysis)
    insights_df = build_insights_df(analysis)

    dfs = {
        "Precios": prices_df,
        "Fees": fees_df,
        "Promociones": promos_df,
        "Resumen_Plataformas": summary_df,
        "Análisis_Geográfico": geo_df,
        "Top_5_Insights": insights_df,
    }

    # Print stats
    print(f"\n--- Estadísticas ---")
    for name, df in dfs.items():
        print(f"  {name}: {len(df)} filas x {len(df.columns)} columnas")

    # Export
    ts = datetime.now().strftime(TIMESTAMP_FORMAT)
    excel_path = REPORTS_DIR / f"competitive_data_{ts}.xlsx"
    export_to_excel(dfs, excel_path)
    export_to_csv(dfs, REPORTS_DIR)

    print(f"\nArchivos listos para Power BI:")
    print(f"  Excel: {excel_path}")
    print(f"  CSVs:  {REPORTS_DIR / 'csv' / '*.csv'}")


if __name__ == "__main__":
    main()
