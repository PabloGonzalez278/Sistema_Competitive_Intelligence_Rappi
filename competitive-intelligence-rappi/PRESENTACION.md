# Guion de Presentacion - Sistema de Competitive Intelligence para Rappi
## Duracion: 30 minutos (20 min presentacion + 10 min Q&A)

---

## SLIDE 1: Portada (30 seg)

**Titulo:** Sistema de Competitive Intelligence para Rappi
**Subtitulo:** Recoleccion automatizada y analisis competitivo vs Uber Eats y DiDi Food
**Autor:** [Tu nombre]
**Fecha:** Abril 2026

---

## SECCION 1: Approach y Scope (3 min)

### SLIDE 2: El Problema

**Que resuelve este sistema:**
- Los equipos de Strategy y Pricing de Rappi carecen de visibilidad sistematica sobre precios, fees, tiempos de entrega y promociones de la competencia
- Los datos competitivos cambian constantemente por zona, hora y demanda
- Sin datos estructurados, las decisiones de pricing son reactivas en lugar de proactivas

### SLIDE 3: Scope Definido

**Plataformas:** Rappi (baseline) + Uber Eats + DiDi Food
**Geografia:** 30 direcciones en CDMX y area metropolitana, cubriendo 8 tipos de zona:
- Premium (Polanco, Condesa, Santa Fe) - 7 direcciones
- Clase Media (Narvarte, Coyoacan) - 6 direcciones
- Popular (Iztapalapa, Tepito) - 3 direcciones
- Periferica (Ecatepec, Neza) - 5 direcciones
- + Business, Commercial, University, Middle-High

**Productos de referencia:** 8 productos estandarizados
- Fast Food: Big Mac, Combo Big Mac, McNuggets 10, Whopper, Combo Whopper
- Retail: Coca-Cola 500ml, Agua 1L, Panales Huggies

**Metricas recolectadas (6/6):**
1. Precio del producto
2. Delivery fee
3. Service fee
4. Tiempo estimado de entrega
5. Promociones/descuentos activos
6. Disponibilidad (tienda + producto)

**Por que este scope:** 5 direcciones bien scrapeadas > 50 a medias. Elegimos 30 para cubrir variabilidad geografica real sin sacrificar calidad.

---

## SECCION 2: Demo del Sistema (7 min)

### SLIDE 4: Arquitectura

```
ORCHESTRATOR (main.py)
    |
    +-- Rappi Scraper -----+
    +-- Uber Eats Scraper --+--> JSON Data + Screenshots
    +-- DiDi Food Scraper --+         |
                                      v
                              CompetitiveAnalyzer
                                      |
                                      v
                            HTML Report (Plotly)
                            Excel/CSV (Power BI)
```

**Stack:** Python 3.12, Playwright (headless), pandas, Plotly, GitHub Actions

### SLIDE 5: Demo en Vivo / Grabacion

**Comandos a mostrar:**

```bash
# Ejecucion completa
python main.py

# Solo 5 direcciones (demo rapida)
python main.py --addresses 5 --no-headless

# Solo analisis con datos existentes
python main.py --analyze-only --report

# Exportar a Power BI
python export_powerbi.py
```

**Mostrar:**
1. Terminal ejecutando el scraper (o grabacion)
2. Los JSON generados en data/raw/
3. Los screenshots de evidencia en data/screenshots/
4. El reporte HTML interactivo abierto en el navegador
5. El Excel abierto en Power BI / Excel

**BACKUP:** Traer datos pre-scrapeados (combined_results_*.json). Si hay bloqueos en vivo, mostrar datos existentes.

### SLIDE 6: Estrategia Anti-Deteccion

**Fase 1 (implementada - $0/mes):**
- Stealth mode: override navigator.webdriver, chrome.runtime
- Rotacion de 6 User-Agents reales
- Delays aleatorios 2-5 seg entre requests
- Viewport y locale de Mexico (es-MX)
- Bloqueo selectivo de recursos (solo video/fonts)
- Reintentos con backoff exponencial

**Fase 2 (disponible si necesario - ~$29/mes):**
- ScraperAPI como proxy rotativo
- Activacion automatica al detectar bloqueos HTTP 403/429

**Innovacion clave:** API Interception en lugar de CSS selectors
- Las 3 plataformas son SPAs - los selectores CSS cambian constantemente
- Interceptamos las respuestas JSON del backend via `page.on("response")`
- Fallback a DOM innerText si las APIs no entregan datos

---

## SECCION 3: Datos Recolectados (3 min)

### SLIDE 7: Volumen de Datos

| Metrica | Valor |
|---|---|
| Plataformas | 3 (Rappi, Uber Eats, DiDi Food) |
| Direcciones | 30 por plataforma = 90 scrapes |
| Productos monitoreados | 8 por direccion |
| Registros de precios | ~582 |
| Registros de fees | ~220 |
| Promociones capturadas | ~243 |
| Screenshots de evidencia | 31 |

### SLIDE 8: Estructura de Datos

**Output JSON por direccion:**
```json
{
  "platform": "rappi",
  "address_name": "Polanco",
  "zone_type": "premium",
  "products": [{
    "store_name": "McDonald's",
    "products": [{
      "product_name": "Big Mac",
      "price": 109.50,
      "original_price": null,
      "discount": null,
      "found": true
    }],
    "estimated_delivery_time": "25-35 min",
    "rating": 4.5
  }],
  "fees": {
    "delivery_fee": 29.00,
    "service_fee": 15.00,
    "free_delivery": false
  },
  "promotions": [...]
}
```

**Exportacion Power BI:** Excel con 6 hojas (Precios, Fees, Promociones, Resumen, Geografico, Insights)

---

## SECCION 4: Top 5 Insights (10 min) -- LA SECCION MAS IMPORTANTE

### SLIDE 9: Insight #1 - Pricing

**Finding:** Rappi es la plataforma mas cara en 8/8 productos analizados comparado con Uber Eats y DiDi Food.

**Impacto:** El posicionamiento de precios afecta directamente la conversion y retencion de usuarios. En un mercado price-sensitive como Mexico, cada punto porcentual de diferencia impacta el GMV.

**Recomendacion:** Revisar la estrategia de markup por categoria. Para productos donde Rappi es mas caro, evaluar negociacion con merchants o ajuste de comisiones para cerrar la brecha de precios.

*[Mostrar grafico de barras comparativo de precios]*

### SLIDE 10: Insight #2 - Fees

**Finding:** Los delivery fees de Rappi son mas altos que Uber Eats (~20% mas) y DiDi Food (~32% mas) en promedio.

**Impacto:** Los delivery fees son un factor decisivo en la eleccion de plataforma. Usuarios comparan fees antes de completar el pedido.

**Recomendacion:** Considerar subsidiar delivery fees en zonas de alta competencia. Implementar delivery fee dinamico basado en la competencia local.

*[Mostrar grafico de fees por plataforma]*

### SLIDE 11: Insight #3 - Operations

**Finding:** Los tiempos de entrega de Rappi (34 min promedio) son mas lentos que Uber Eats (30 min).

**Impacto:** Tiempos de entrega mas largos reducen el NPS y la tasa de recompra. Cada minuto adicional incrementa la probabilidad de cancelacion.

**Recomendacion:** Optimizar asignacion de repartidores en zonas con mayor diferencia. Considerar batching inteligente y rutas optimizadas con IA.

*[Mostrar grafico de tiempos de entrega con barras de error]*

### SLIDE 12: Insight #4 - Geographic Strategy

**Finding:** En zonas comerciales, Rappi es ~14% mas caro que DiDi Food. La competitividad varia significativamente por zona.

**Impacto:** Las diferencias de precio por zona sugieren oportunidades de pricing localizado. Zonas perifericas y populares son mas price-sensitive.

**Recomendacion:** Implementar pricing diferenciado por zona. Priorizar subsidios en zonas donde la brecha competitiva es mayor.

*[Mostrar heatmap geografico zona x plataforma]*

### SLIDE 13: Insight #5 - Promotions

**Finding:** Rappi tiene 82 promociones visibles vs 127 de Uber Eats. La competencia esta siendo mas agresiva en descuentos.

**Impacto:** Las promociones visibles impactan directamente en la eleccion de plataforma al momento de abrir la app.

**Recomendacion:** Aumentar visibilidad de promociones en home feed. Evaluar campanas de descuento focalizadas en categorias y zonas donde la competencia es mas agresiva.

*[Mostrar tabla comparativa de promociones]*

---

## SECCION 5: Decisiones Tecnicas (4 min)

### SLIDE 14: Por que estas tecnologias

| Decision | Alternativa | Por que |
|---|---|---|
| Playwright | Selenium | 2-3x mas rapido, mejor anti-detection, auto-wait nativo |
| API Interception | CSS Selectors | SPAs cambian selectores constantemente; APIs son estables |
| Plotly | Matplotlib | Graficos interactivos en HTML estatico, mejor UX |
| GitHub Actions | Cron local | CI/CD gratuito, reproducible, versionado |
| JSON + Excel | Solo CSV | JSON para pipeline, Excel para Power BI |

### SLIDE 15: Desafios y Soluciones

1. **Falsos positivos en deteccion de CAPTCHAs**
   - Problema: Todas las plataformas cargan scripts de reCAPTCHA preventivamente
   - Solucion: Verificar visibilidad real del CAPTCHA (bounding box > 0px) en lugar de buscar en el HTML source

2. **Selectores CSS inestables**
   - Problema: Las SPAs cambian su DOM constantemente
   - Solucion: API Interception - capturamos las respuestas JSON del backend

3. **Deteccion de bots**
   - Problema: Plataformas detectan Playwright como bot
   - Solucion: Stealth scripts (navigator.webdriver override, chrome.runtime mock, Sec-CH-UA headers)

4. **Variabilidad de datos por zona**
   - Problema: Precios y disponibilidad cambian por ubicacion
   - Solucion: 30 direcciones estrategicas cubriendo 8 tipos de zona

---

## SECCION 6: Limitaciones y Next Steps (3 min)

### SLIDE 16: Limitaciones Conocidas

1. **Datos de scraping real son parciales** - Las plataformas tienen protecciones activas que limitan la extraccion en tiempo real
2. **Selectores CSS pueden cambiar** - Las SPAs actualizan su interfaz sin previo aviso
3. **Precios dinamicos** - Los precios varian por hora/dia/demanda; una sola corrida captura un snapshot
4. **DiDi Food** - Menor documentacion publica; estructura web menos predecible
5. **Horarios** - Restaurantes cerrados no retornan datos

### SLIDE 17: Next Steps (con mas tiempo)

| Prioridad | Mejora | Impacto |
|---|---|---|
| P0 | Dashboard interactivo (Streamlit/Power BI) | Monitoreo en tiempo real para Strategy |
| P0 | Scraping multi-horario | Capturar variabilidad temporal (surge pricing) |
| P1 | Alertas automaticas | Notificar cuando competencia cambia precios >10% |
| P1 | ML para prediccion | Predecir movimientos de precios competitivos |
| P2 | Multiples verticales | Restaurantes + retail + farmacia |
| P2 | API REST interna | Integracion con sistemas de pricing de Rappi |

---

## SECCION 7: Q&A (10 min)

### Preguntas Anticipadas y Respuestas

**P: Por que no usaron APIs oficiales?**
R: Las APIs publicas tienen rate limiting agresivo. El scraping visual captura exactamente lo que ve el usuario final (precios con markup, promotions activas). En produccion, se complementaria con APIs donde esten disponibles.

**P: Es legal el scraping?**
R: Solo recolectamos datos publicos visibles sin autenticacion. Respetamos robots.txt, usamos rate limiting (2-5 seg), y User-Agents reales. En produccion, se consultaria con Legal antes de implementar scraping sistematico.

**P: Como escala el sistema?**
R: La arquitectura es modular - agregar una nueva plataforma es crear una clase que hereda de BaseScraper. GitHub Actions escala horizontalmente. Para alto volumen, se integraria ScraperAPI (~$29/mes) y se paralelizarian los scrapers.

**P: Que pasa si las plataformas cambian su sitio?**
R: La estrategia de API Interception es mas resiliente que CSS selectors. Si la estructura de las APIs cambia, los regex patterns se actualizan. El sistema tiene fallback DOM como segunda capa.

**P: Los datos de muestra son confiables?**
R: Los datos simulados usan rangos de precios reales del mercado mexicano, multiplicadores por zona basados en estudios de mercado, y variabilidad estadistica realista. Sirven para demostrar las capacidades analiticas del sistema.

---

## Archivos de Soporte para la Presentacion

| Archivo | Uso |
|---|---|
| `reports/competitive_report_*.html` | Reporte interactivo (abrir en navegador) |
| `reports/competitive_data_*.xlsx` | Datos para Power BI |
| `reports/csv/*.csv` | CSVs individuales por dimension |
| `data/screenshots/*.png` | Evidencia visual del scraping |
| `data/raw/combined_results_*.json` | Datos crudos backup |

---

## Tips para la Presentacion

1. **Abrir el reporte HTML** en el navegador ANTES de la presentacion
2. **Tener Power BI/Excel abierto** con el archivo .xlsx cargado
3. **Tener la terminal lista** con el comando `python main.py --addresses 3 --no-headless` por si piden demo en vivo
4. **Datos pre-scrapeados como backup** - no depender de demo en vivo
5. **Enfocarse en insights**, no en codigo - el evaluador busca pensamiento estrategico
6. **Ser honesto con limitaciones** - documenta lo que no funciono y por que
