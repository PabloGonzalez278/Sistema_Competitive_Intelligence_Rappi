# 🏆 Sistema de Competitive Intelligence para Rappi

Sistema automatizado de recolección y análisis de datos competitivos para Rappi, comparando precios, fees, tiempos de entrega y promociones contra **Uber Eats** y **DiDi Food** en México (CDMX y área metropolitana).

---

## 📋 Tabla de Contenidos

- [Arquitectura](#-arquitectura)
- [Setup Rápido](#-setup-rápido)
- [Cómo Ejecutar el Scraper](#-cómo-ejecutar-el-scraper)
- [Cómo Generar el Informe](#-cómo-generar-el-informe)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Decisiones Técnicas](#-decisiones-técnicas)
- [Estrategia Anti-Detección](#-estrategia-anti-detección)
- [Cobertura Geográfica](#-cobertura-geográfica)
- [Productos de Referencia](#-productos-de-referencia)
- [Consideraciones Éticas](#-consideraciones-éticas)
- [Limitaciones Conocidas](#-limitaciones-conocidas)
- [Costos](#-costos)
- [GitHub Actions (Automatización)](#-github-actions)

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────┐
│              ORCHESTRATOR (main.py)              │
│   CLI args → Load Config → Run Scrapers → Report│
└──────┬──────────────┬──────────────┬────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌───────────┐
│  Rappi   │  │  Uber Eats   │  │ DiDi Food │
│ Scraper  │  │   Scraper    │  │  Scraper  │
└────┬─────┘  └──────┬───────┘  └─────┬─────┘
     │               │               │
     └───────┬───────┴───────┬───────┘
             ▼               ▼
      ┌────────────┐  ┌──────────────┐
      │  JSON Raw   │  │  Screenshots │
      │   Data      │  │  (evidencia) │
      └──────┬─────┘  └──────────────┘
             ▼
     ┌───────────────┐
     │   Analyzer    │
     │  (insights)   │
     └───────┬───────┘
             ▼
     ┌───────────────┐
     │  HTML Report  │
     │  (Plotly)     │
     └───────────────┘
```

**Stack Tecnológico:**
| Componente | Tecnología | Justificación |
|---|---|---|
| Scraping | **Playwright** | Soporte headless robusto, manejo de SPAs, anti-detection |
| Anti-detection | User-Agent rotation, delays, **ScraperAPI** (fase 2) | Balance costo/robustez |
| Análisis | **pandas**, estadísticas nativas Python | Ligero, sin dependencias pesadas |
| Visualización | **Plotly** | Gráficos interactivos embebidos en HTML |
| Automatización | **GitHub Actions** | CI/CD gratuito, cron scheduling |
| Lenguaje | **Python 3.12** | Ecosistema maduro para scraping/análisis |

---

## 🚀 Setup Rápido

### Prerrequisitos
- Python 3.11+
- pip

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/<tu-usuario>/competitive-intelligence-rappi.git
cd competitive-intelligence-rappi

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar Playwright browsers
playwright install chromium
```

### Variables de Entorno (opcionales)

```bash
# Solo si necesitas proxies (Fase 2)
export SCRAPER_API_KEY="tu_api_key"
export USE_PROXY="true"

# Nivel de logging
export LOG_LEVEL="DEBUG"  # default: INFO
```

---

## 🕷️ Cómo Ejecutar el Scraper

### Ejecución completa (3 plataformas, 30 direcciones)
```bash
python main.py
```

### Opciones disponibles

```bash
# Solo plataformas específicas
python main.py --platforms rappi uber_eats

# Limitar número de direcciones (útil para testing)
python main.py --addresses 5

# Con navegador visible (debug)
python main.py --no-headless --addresses 3

# Solo generar análisis con datos existentes
python main.py --analyze-only

# Solo generar informe HTML
python main.py --report
```

### Output

Los datos se guardan en `data/raw/`:
- `rappi_YYYY-MM-DD_HH-MM-SS.json` - Datos de Rappi
- `uber_eats_YYYY-MM-DD_HH-MM-SS.json` - Datos de Uber Eats
- `didi_food_YYYY-MM-DD_HH-MM-SS.json` - Datos de DiDi Food
- `combined_results_YYYY-MM-DD_HH-MM-SS.json` - Todos combinados

Screenshots de evidencia en `data/screenshots/`.

---

## 📊 Cómo Generar el Informe

```bash
# Generar informe con datos existentes
python main.py --analyze-only --report

# Exportar datos a Excel/CSV para Power BI
python export_powerbi.py
```

### Exportación Power BI

El script `export_powerbi.py` genera:
- **Excel** (`reports/competitive_data_*.xlsx`) con 6 hojas:
  - `Precios` - 582+ registros de precios por producto/plataforma/zona
  - `Fees` - 220+ registros de delivery y service fees
  - `Promociones` - 240+ promociones capturadas
  - `Resumen_Plataformas` - KPIs agregados por plataforma
  - `Análisis_Geográfico` - Métricas por zona y plataforma
  - `Top_5_Insights` - Insights accionables con Finding/Impacto/Recomendación
- **CSVs** individuales en `reports/csv/` para importación directa

El informe HTML interactivo se genera en `reports/competitive_report_*.html` e incluye:

1. **Resumen de cobertura** - Métricas de scraping por plataforma
2. **Top 5 Insights Accionables** - Finding, Impacto, Recomendación
3. **Comparación de Precios** - Gráfico de barras por producto
4. **Comparación de Fees** - Delivery fee y service fee
5. **Tiempos de Entrega** - Por plataforma con rangos
6. **Heatmap Geográfico** - Precios por zona y plataforma
7. **Disponibilidad** - Tasa de éxito por plataforma

---

## 📁 Estructura del Proyecto

```
competitive-intelligence-rappi/
├── main.py                          # Orquestador principal
├── generate_sample_data.py          # Generador de datos de muestra
├── export_powerbi.py                # Exportador Excel/CSV para Power BI
├── PRESENTACION.md                  # Guión de presentación (30 min)
├── requirements.txt                 # Dependencias Python
├── README.md                        # Este archivo
├── .gitignore
│
├── config/
│   ├── settings.py                  # Configuración central
│   ├── addresses.json               # 30 direcciones en CDMX
│   └── products.json                # Productos de referencia
│
├── scrapers/
│   ├── base_scraper.py              # Clase base (navegación, retry, screenshots)
│   ├── rappi_scraper.py             # Scraper de Rappi
│   ├── ubereats_scraper.py          # Scraper de Uber Eats
│   └── didifood_scraper.py          # Scraper de DiDi Food
│
├── utils/
│   ├── anti_detection.py            # User-Agent rotation, delays, proxy
│   └── logger.py                    # Logging centralizado (Rich + file)
│
├── analysis/
│   ├── analyzer.py                  # Motor de análisis competitivo
│   └── visualizations.py            # Gráficos Plotly + informe HTML
│
├── tests/
│   └── test_scrapers.py             # Tests unitarios
│
├── data/
│   ├── raw/                         # JSON output del scraping
│   └── screenshots/                 # Capturas de pantalla
│
├── reports/                         # Informes HTML generados
├── logs/                            # Logs de ejecución
│
└── .github/
    └── workflows/
        └── scrape.yml               # GitHub Actions (cron L/Mi/V)
```

---

## 🧠 Decisiones Técnicas

### ¿Por qué Playwright en lugar de Selenium?
- **Velocidad**: Playwright es 2-3x más rápido en ejecución headless
- **Anti-detection**: Mejor soporte para fingerprinting avoidance
- **SPAs**: Las 3 plataformas son SPAs con carga dinámica de contenido
- **Estabilidad**: Auto-wait integrado reduce flakiness

### ¿Por qué no APIs?
- Las APIs públicas de estas plataformas tienen rate limiting agresivo
- El scraping visual captura exactamente lo que ve el usuario (precios finales, promotions)
- Complementario: se puede integrar API scraping en futuras versiones

### ¿Por qué Plotly en lugar de Matplotlib para el informe?
- Gráficos **interactivos** (hover, zoom) embebidos en HTML
- No requiere servidor (funciona como archivo estático)
- Mejor UX para equipos de Strategy y Pricing

---

## 🛡️ Estrategia Anti-Detección

### Fase 1: Sin proxies (baseline)
- Rate limiting: 2-5 segundos entre requests
- Rotación de User-Agents (6 browsers reales)
- Bloqueo de recursos innecesarios (imágenes, fonts)
- Viewport aleatorio
- Locale y timezone de México
- Reintentos automáticos con backoff exponencial

### Fase 2: Con proxies (si hay bloqueos)
- **ScraperAPI** como proxy rotativo
- Activación automática al detectar CAPTCHAs o HTTP 403/429
- Integración transparente (solo cambiar variable de entorno)

---

## 📍 Cobertura Geográfica

**30 direcciones** en CDMX y área metropolitana, seleccionadas para cubrir:

| Tipo de Zona | Cantidad | Ejemplos |
|---|---|---|
| Premium (alto ingreso) | 7 | Polanco, Condesa, Roma Norte, Santa Fe, Lomas, Pedregal, Interlomas |
| Clase Media Alta | 3 | Del Valle, Satélite, Cuajimalpa |
| Clase Media | 6 | Narvarte, Coyoacán, Tlalpan, Coapa, Tacubaya, Mixcoac |
| Zona de Oficinas | 2 | Reforma, Insurgentes Sur |
| Comercial | 2 | Centro Histórico, Zona Rosa |
| Estudiantil | 2 | UNAM, IPN Zacatenco |
| Popular | 3 | Iztapalapa, Tepito, Azcapotzalco |
| Periférica | 5 | Ciudad Neza, Ecatepec, Xochimilco, Tláhuac, Lindavista |

**Justificación**: Esta distribución captura la variabilidad de precios, disponibilidad y tiempos de entrega entre zonas de diferente poder adquisitivo y densidad operativa.

---

## 🛒 Productos de Referencia

### Fast Food (McDonald's / Burger King)
| Producto | ID | Rango esperado (MXN) |
|---|---|---|
| Big Mac | ff_01 | $79 - $120 |
| Combo Mediano Big Mac | ff_02 | $139 - $199 |
| McNuggets 10 pzas | ff_03 | $89 - $140 |
| Whopper | ff_04 | $89 - $130 |
| Combo Whopper Mediano | ff_05 | $149 - $210 |

### Retail (Tienda de conveniencia)
| Producto | ID | Rango esperado (MXN) |
|---|---|---|
| Coca-Cola 500ml | rt_01 | $18 - $35 |
| Agua embotellada 1L | rt_02 | $12 - $28 |
| Pañales Huggies Ultra Confort | rt_03 | $180 - $350 |

---

## ⚖️ Consideraciones Éticas

1. **robots.txt**: Se respeta cuando es posible
2. **Rate limiting**: Delays de 2-5 segundos entre cada request
3. **User-Agents**: Se usan User-Agents reales de navegadores comunes
4. **No sobrecarga**: Ejecución secuencial entre plataformas para evitar picos
5. **Datos públicos**: Solo se recolectan datos visibles al usuario sin autenticación
6. **Uso interno**: Datos para análisis competitivo, no redistribución
7. **Disclaimer legal**: En producción, consultar con Legal antes de implementar scraping sistemático

---

## ⚠️ Limitaciones Conocidas

1. **SPAs dinámicas**: Los selectores CSS pueden cambiar sin previo aviso
2. **Geolocalización**: Algunas plataformas pueden no respetar coordenadas vía URL
3. **CAPTCHAs**: Plataformas pueden presentar CAPTCHAs bajo carga
4. **Disponibilidad**: Restaurantes pueden estar cerrados según horario
5. **Precios dinámicos**: Los precios pueden variar por hora/día/demanda
6. **DiDi Food**: Menor documentación pública de su estructura web
7. **Productos**: No todos los productos de referencia están disponibles en todas las tiendas

---

## 💰 Costos

| Servicio | Costo | Cuándo se usa |
|---|---|---|
| GitHub Actions | **Gratis** (2000 min/mes) | Siempre |
| ScraperAPI | **$0** (Fase 1) / **~$29/mes** starter (Fase 2) | Solo si hay bloqueos |
| Playwright | **Gratis** | Siempre |

**Costo total Fase 1: $0/mes**

---

## 🤖 GitHub Actions

El workflow está configurado para ejecutarse:
- **Manualmente**: Via `workflow_dispatch` con parámetros configurables
- **Programado**: Lunes, Miércoles y Viernes a las 10:00 AM CST

### Configurar Secrets

En tu repositorio de GitHub, agrega estos secrets (solo si usas Fase 2):
- `SCRAPER_API_KEY`: Tu API key de ScraperAPI
- `USE_PROXY`: `true` para activar proxies

### Ejecución Manual

```bash
gh workflow run scrape.yml -f platforms="rappi uber_eats" -f addresses="10"
```

---

## 🧪 Tests

```bash
# Ejecutar tests
pytest tests/ -v

# Con cobertura
pytest tests/ -v --tb=short
```

---

## 🔮 Next Steps (con más tiempo)

1. **Dashboard interactivo con Streamlit/Power BI** para monitoreo en tiempo real
2. **Scraping de múltiples verticales** (restaurantes + retail + farmacia)
3. **Análisis temporal** con múltiples corridas para detectar tendencias
4. **Alertas automáticas** cuando la competencia cambia precios significativamente
5. **ML para predicción** de movimientos de precios competitivos
6. **API REST** para integración con sistemas internos de Rappi
7. **Comparación de mismo restaurante** en diferentes plataformas
8. **Integración con Power BI** para dashboard corporativo

---

**Desarrollado como caso técnico para el rol de AI Engineer en Rappi.**
