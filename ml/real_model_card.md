# Model card: baseline real de ocurrencia de incendios por zona y temporada

Versión: `conaf-real-baseline-0.1.0`. Fecha: `2026-11-14T02:15:38.119125+00:00`. Semilla: `42`.

## Descripción

Modelo de clasificación binaria que estima la probabilidad de que una zona censal/municipal de la Región de Valparaíso tenga al menos un punto de ignición CONAF en una temporada. Se entrenó con datos reales 2010-2025 y validación temporal/espacial.

**Estado: baseline de investigación. No es un modelo operativo y no está integrado en la API.**

## Uso previsto

- Comparar enfoques de modelado y medir si la historia de incendios y las variables estáticas/climáticas tienen señal.
- Generar hipótesis para priorizar la ampliación de la capa de zonas y la ingeniería de variables.
- Docencia y revisión metodológica CRISP-DM.

## Uso no previsto

- Despacho de brigadas, alertas públicas, seguros o priorización presupuestaria con consecuencias reales.
- Zonas fuera de la capa de 560 polígonos o fuera de la Región de Valparaíso continental.
- Inferencia causal sobre causas de incendio.

## Datos

- Etiquetas: CONAF, puntos de inicio por temporada, 2010_2011..2024_2025.
- Zonas: 560 polígonos; área 613.7 km²; cobertura 3.74% del área regional.
- Filas: 7840; positivos: 1500; prevalencia: 0.191.
- Clima: NASA POWER (MERRA-2), centroide comunal (respaldo por límite de Open-Meteo); temporada previa y anomalía 1991-2020.
- Combustible: CONAF Catastro de Uso de Suelo y Vegetación 2019, estático.

## Variables

Combustible nativo/plantación/matorral/pradera/agrícola/urbano, vegetación, pendiente, superficie, población, elevación, centroide, historia de incendios previos (última, 3, 5 temporadas, tasa, tiempo desde el último), agregados comunales previos y clima de la temporada previa. Se excluyen agregados de todo el período y cualquier dato de la temporada objetivo.

## Validación

- Leave-one-season-out (14 folds).
- Leave-one-province-out (7 provincias).
- `StratifiedGroupKFold` por comuna (5 folds).
- Métricas: PR-AUC, ROC-AUC, Brier, log-loss, precision, recall, F1, matrices de confusión.

## Rendimiento (LOSO)

| Métrica | Media | Desv. estándar | IC95% |
|---|---|---|---|
| PR-AUC | 0.635 | 0.126 | 0.563–0.708 |
| ROC-AUC | 0.860 | 0.031 | 0.842–0.878 |
| Brier | 0.113 | 0.013 | 0.106–0.121 |

Prevalencia de referencia (PR-AUC basal): **0.191**. Regla histórica: **0.537**.
Validación espacial: PR-AUC provincia **0.571**, comuna **0.654**.

## Calibración y umbrales

Método: **sigmoid**. Brier calibrado OOF: **0.107**. ECE: **0.023**.

Los umbrales operativos se justifican por precision/recall, no por argmax. Ver `real_training_report.md` y `real_metrics.json`.

## Limitaciones

- No es un modelo operativo: es un baseline de investigación con cobertura espacial parcial.
- Las zonas cubren ~3.7% del área; los incendios fuera de zona no se etiquetan.
- No usa clima de la temporada objetivo, causas de ignición, caminos, líneas eléctricas ni capacidad de respuesta.
- Clima de la temporada previa desde NASA POWER (MERRA-2), centroide comunal (respaldo por límite de Open-Meteo); resolución de grilla gruesa en el centroide comunal, no microclima local.
- Los combustibles son un corte estático CONAF 2019; las plantaciones y el uso de suelo cambian.
- La selección del modelo y las métricas comparten folds; las métricas del elegido son optimistas.
- La validación espacial por provincia/comuna es un estrés de generalización, no una estimación de despliegue.
- El combustible/vegetación es un corte 2019 y la población es censo 2017; en temporadas previas son información futura, un supuesto estático fuerte.
- El modelo puede aprender principalmente qué zonas tienen historia recurrente de incendios; eso no equivale a predecir ignición.
- La etiqueta no distingue tamaño, severidad, causa ni impacto.
- La validación espacial muestra degradación; no se debe extrapolar a comunas o zonas sin historia.
- Los datos CONAF pueden tener subregistro y coordenadas imprecisas.

## Consideraciones éticas

No usar para estigmatizar zonas ni para asignar recursos sin revisión humana. Las predicciones son probabilísticas y agregadas; no identifican personas. Cualquier uso operativo requiere validación independiente, análisis de costo-beneficio y supervisión de expertos.

## Reproducibilidad

```bash
uv run python scripts/crispdm_real_model.py all
uv run pytest tests/test_crispdm_real_model.py -o addopts=''
```

El artefacto incluye el pipeline completo, la lista de variables, los umbrales y los metadatos. No se debe cargar en producción sin una revisión explícita.
