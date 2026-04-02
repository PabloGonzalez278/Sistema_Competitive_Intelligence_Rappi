"""
Motor de visualizaciones y generación de informes HTML.
Genera gráficos comparativos y un informe ejecutivo interactivo.
"""
import json
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from config.settings import REPORTS_DIR, TIMESTAMP_FORMAT
from utils.logger import get_logger

log = get_logger("visualizations")

PLATFORM_COLORS = {
    "rappi": "#FF441F",
    "uber_eats": "#06C167",
    "didi_food": "#FF8C00",
}

PLATFORM_NAMES = {
    "rappi": "Rappi",
    "uber_eats": "Uber Eats",
    "didi_food": "DiDi Food",
}


def create_price_comparison_chart(analysis: dict) -> str:
    """Gráfico de barras comparando precios por producto y plataforma."""
    price_data = analysis.get("price_comparison", {})
    if not price_data:
        return ""

    products = []
    platforms_data = {}

    for key, data in price_data.items():
        product_label = f"{data['store']} - {data['product']}"
        products.append(product_label)
        for platform, prices in data.get("prices_by_platform", {}).items():
            if platform not in platforms_data:
                platforms_data[platform] = []
            platforms_data[platform].append(prices.get("avg", 0))

    # Asegurar que todas las plataformas tengan el mismo número de entries
    for platform in platforms_data:
        while len(platforms_data[platform]) < len(products):
            platforms_data[platform].append(0)

    fig = go.Figure()
    for platform, prices in platforms_data.items():
        fig.add_trace(go.Bar(
            name=PLATFORM_NAMES.get(platform, platform),
            x=products,
            y=prices,
            marker_color=PLATFORM_COLORS.get(platform, "#999"),
            text=[f"${p:.0f}" if p > 0 else "N/A" for p in prices],
            textposition="auto",
        ))

    fig.update_layout(
        title="Comparación de Precios por Producto y Plataforma (MXN)",
        xaxis_title="Producto",
        yaxis_title="Precio Promedio (MXN)",
        barmode="group",
        template="plotly_white",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_fee_comparison_chart(analysis: dict) -> str:
    """Gráfico comparativo de fees entre plataformas."""
    fee_data = analysis.get("fee_comparison", {})
    if not fee_data:
        return ""

    platforms = []
    delivery_fees = []
    service_fees = []

    for platform, data in fee_data.items():
        platforms.append(PLATFORM_NAMES.get(platform, platform))
        delivery_fees.append(data.get("delivery_fee", {}).get("avg", 0) or 0)
        service_fees.append(data.get("service_fee", {}).get("avg", 0) or 0)

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Delivery Fee Promedio", "Service Fee Promedio"))

    colors = [PLATFORM_COLORS.get(p, "#999") for p in fee_data.keys()]

    fig.add_trace(go.Bar(
        x=platforms, y=delivery_fees,
        marker_color=colors,
        text=[f"${f:.0f}" for f in delivery_fees],
        textposition="auto",
        showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=platforms, y=service_fees,
        marker_color=colors,
        text=[f"${f:.0f}" for f in service_fees],
        textposition="auto",
        showlegend=False,
    ), row=1, col=2)

    fig.update_layout(
        title="Comparación de Fees entre Plataformas (MXN)",
        template="plotly_white",
        height=400,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_delivery_time_chart(analysis: dict) -> str:
    """Gráfico de tiempos de entrega por plataforma."""
    time_data = analysis.get("delivery_time_comparison", {})
    if not time_data:
        return ""

    platforms = []
    avg_times = []
    min_times = []
    max_times = []

    for platform, data in time_data.items():
        if data.get("avg_minutes"):
            platforms.append(PLATFORM_NAMES.get(platform, platform))
            avg_times.append(data["avg_minutes"])
            min_times.append(data.get("min_minutes", 0))
            max_times.append(data.get("max_minutes", 0))

    fig = go.Figure()

    colors = [PLATFORM_COLORS.get(p, "#999") for p in time_data.keys() if time_data[p].get("avg_minutes")]

    fig.add_trace(go.Bar(
        x=platforms, y=avg_times,
        marker_color=colors,
        text=[f"{t:.0f} min" for t in avg_times],
        textposition="auto",
        error_y=dict(
            type="data",
            symmetric=False,
            array=[max_t - avg_t for max_t, avg_t in zip(max_times, avg_times)],
            arrayminus=[avg_t - min_t for avg_t, min_t in zip(avg_times, min_times)],
        ),
    ))

    fig.update_layout(
        title="Tiempo Promedio de Entrega por Plataforma (minutos)",
        yaxis_title="Minutos",
        template="plotly_white",
        height=400,
        showlegend=False,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_geographic_heatmap(analysis: dict) -> str:
    """Heatmap de competitividad por zona geográfica."""
    geo_data = analysis.get("geographic_analysis", {})
    if not geo_data:
        return ""

    zones = list(geo_data.keys())
    platforms = set()
    for zone_data in geo_data.values():
        platforms.update(zone_data.keys())
    platforms = sorted(platforms)

    # Matriz de precios promedio
    z_values = []
    for zone in zones:
        row = []
        for platform in platforms:
            data = geo_data[zone].get(platform, {})
            row.append(data.get("avg_price") or 0)
        z_values.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=[PLATFORM_NAMES.get(p, p) for p in platforms],
        y=[z.replace("_", " ").title() for z in zones],
        colorscale="RdYlGn_r",
        text=[[f"${v:.0f}" if v > 0 else "N/A" for v in row] for row in z_values],
        texttemplate="%{text}",
        hovertemplate="Zona: %{y}<br>Plataforma: %{x}<br>Precio Prom: %{text}<extra></extra>",
    ))

    fig.update_layout(
        title="Precio Promedio por Zona y Plataforma (MXN)",
        template="plotly_white",
        height=450,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_availability_chart(analysis: dict) -> str:
    """Gráfico de disponibilidad por plataforma."""
    avail_data = analysis.get("availability_analysis", {})
    if not avail_data:
        return ""

    platforms = []
    store_rates = []
    product_rates = []

    for platform, data in avail_data.items():
        platforms.append(PLATFORM_NAMES.get(platform, platform))
        store_rates.append(data.get("store_availability_rate", 0))
        product_rates.append(data.get("product_availability_rate", 0))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Tiendas", x=platforms, y=store_rates,
        marker_color="#4ECDC4",
        text=[f"{r:.0f}%" for r in store_rates], textposition="auto",
    ))
    fig.add_trace(go.Bar(
        name="Productos", x=platforms, y=product_rates,
        marker_color="#FF6B6B",
        text=[f"{r:.0f}%" for r in product_rates], textposition="auto",
    ))

    fig.update_layout(
        title="Tasa de Disponibilidad por Plataforma (%)",
        yaxis_title="Disponibilidad (%)",
        barmode="group",
        template="plotly_white",
        height=400,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)


def generate_report(analysis: dict, raw_results: dict) -> Path:
    """Genera informe HTML ejecutivo completo."""
    log.info("Generando informe ejecutivo HTML...")

    # Generar gráficos
    charts = {
        "price_chart": create_price_comparison_chart(analysis),
        "fee_chart": create_fee_comparison_chart(analysis),
        "delivery_chart": create_delivery_time_chart(analysis),
        "geo_heatmap": create_geographic_heatmap(analysis),
        "availability_chart": create_availability_chart(analysis),
    }

    # Generar insights HTML
    insights_html = ""
    for insight in analysis.get("top_insights", []):
        insights_html += f"""
        <div class="insight-card">
            <div class="insight-header">
                <span class="insight-number">#{insight['id']}</span>
                <span class="insight-category">{insight['category']}</span>
            </div>
            <div class="insight-body">
                <h3>🔍 Finding</h3>
                <p>{insight['finding']}</p>
                <h3>💥 Impacto</h3>
                <p>{insight['impact']}</p>
                <h3>✅ Recomendación</h3>
                <p>{insight['recommendation']}</p>
            </div>
        </div>
        """

    # Generar resumen
    summary = analysis.get("summary", {})
    coverage_html = ""
    for platform, coverage in summary.get("data_coverage", {}).items():
        coverage_html += f"""
        <div class="coverage-card">
            <h4 style="color: {PLATFORM_COLORS.get(platform, '#333')}">{PLATFORM_NAMES.get(platform, platform)}</h4>
            <p>Direcciones: {coverage['total_addresses']}</p>
            <p>Exitosos: {coverage['successful_scrapes']} ({coverage['success_rate']}%)</p>
            <p>Productos encontrados: {coverage['products_found']}</p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Competitive Intelligence Report - Rappi</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        .header {{
            background: linear-gradient(135deg, #FF441F 0%, #FF6B4A 100%);
            color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.2em; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; font-size: 1.1em; }}

        .section {{ background: white; border-radius: 12px; padding: 30px; margin-bottom: 25px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
        .section h2 {{ color: #FF441F; margin-bottom: 20px; font-size: 1.5em;
                       border-bottom: 2px solid #FF441F; padding-bottom: 10px; }}

        .coverage-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .coverage-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .coverage-card h4 {{ font-size: 1.2em; margin-bottom: 10px; }}

        .insight-card {{
            background: #f8f9fa; border-left: 4px solid #FF441F;
            padding: 25px; margin-bottom: 20px; border-radius: 0 8px 8px 0;
        }}
        .insight-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 15px; }}
        .insight-number {{ background: #FF441F; color: white; padding: 4px 12px;
                          border-radius: 20px; font-weight: bold; font-size: 0.9em; }}
        .insight-category {{ background: #e8e8e8; padding: 4px 12px;
                            border-radius: 20px; font-size: 0.85em; color: #555; }}
        .insight-body h3 {{ margin: 10px 0 5px; font-size: 1em; }}
        .insight-body p {{ line-height: 1.6; color: #555; }}

        .chart-container {{ margin: 20px 0; }}

        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 0.9em; }}

        @media (max-width: 768px) {{
            .container {{ padding: 10px; }}
            .header {{ padding: 20px; }}
            .header h1 {{ font-size: 1.5em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏆 Competitive Intelligence Report</h1>
            <p>Sistema de Análisis Competitivo - Rappi vs Uber Eats vs DiDi Food</p>
            <p>Fecha: {datetime.now().strftime('%d de %B, %Y - %H:%M hrs')}</p>
        </div>

        <div class="section">
            <h2>📊 Resumen de Cobertura</h2>
            <div class="coverage-grid">
                {coverage_html}
            </div>
        </div>

        <div class="section">
            <h2>🏅 Top 5 Insights Accionables</h2>
            {insights_html}
        </div>

        <div class="section">
            <h2>💰 Comparación de Precios</h2>
            <div class="chart-container">{charts['price_chart']}</div>
        </div>

        <div class="section">
            <h2>🏷️ Comparación de Fees</h2>
            <div class="chart-container">{charts['fee_chart']}</div>
        </div>

        <div class="section">
            <h2>🚀 Tiempos de Entrega</h2>
            <div class="chart-container">{charts['delivery_chart']}</div>
        </div>

        <div class="section">
            <h2>🗺️ Análisis Geográfico</h2>
            <div class="chart-container">{charts['geo_heatmap']}</div>
        </div>

        <div class="section">
            <h2>📦 Disponibilidad</h2>
            <div class="chart-container">{charts['availability_chart']}</div>
        </div>

        <div class="footer">
            <p>Generado por el Sistema de Competitive Intelligence para Rappi</p>
            <p>Datos recolectados de manera ética y responsable</p>
        </div>
    </div>
</body>
</html>"""

    ts = datetime.now().strftime(TIMESTAMP_FORMAT)
    report_path = REPORTS_DIR / f"competitive_report_{ts}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"Informe generado: {report_path}")
    return report_path
