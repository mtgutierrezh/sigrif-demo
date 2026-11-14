# Reporte de entrenamiento: ocurrencia real de incendios por zona y temporada

Generado: `2026-11-14T02:15:38.119125+00:00`. Semilla: `42`. Versión: `conaf-real-baseline-0.1.0`.

## Veredicto honesto

El modelo supera el baseline de prevalencia en PR-AUC, pero la cobertura espacial y la naturaleza retrospectiva de las etiquetas impiden presentarlo como modelo operativo.

- Modelo seleccionado: **random_forest** (regla PR-AUC/Brier).
- PR-AUC LOSO: **0.635**; prevalencia de referencia: **0.191**; regla histórica: **0.537**.
- Brier calibrado out-of-fold: **0.107**; sin calibrar: **0.113**.
- Modelos empatados en PR-AUC (dentro de 0.01): **logistic_regression, random_forest**. Se desempata por menor Brier.
- **No integrar en la API ni usar para decisiones operativas todavía.**

## 1. Comprensión del negocio

La pregunta es si una zona tendrá al menos un punto de ignición CONAF en la temporada siguiente. Es una tarea de clasificación binaria desbalanceada, evaluada temporal y espacialmente. No es un índice de riesgo, peligro, vulnerabilidad ni prioridad de extinción.

## 2. Comprensión de los datos

- Etiquetas: puntos de inicio CONAF por temporada, 2010_2011 a 2024_2025, filtrados a la Región de Valparaíso continental.
- Zonas: 560 polígonos censales/municipales continentales; se excluyen Isla de Pascua y Juan Fernández.
- El EDA completo está en `REAL_EDA.md`; la cobertura de zonas es ~3.7% del área regional y solo ~44% de los puntos CONAF caen dentro de alguna zona.
- La temporada 2010_2011 se usa solo como historia; las filas evaluadas son 2011_2012..2024_2025.

## 3. Preparación de datos

Cada fila es `zona × temporada objetivo`. Las variables de historia usan exclusivamente temporadas anteriores a la objetivo. El clima es de la temporada previa y su anomalía contra la climatología 1991-2020. No se usa `historical_fires`, `incendios_*` ni ningún agregado de todo el período.

- Filas: **7840**; positivos: **1500**; prevalencia: **0.191**.
- Variables numéricas: 37; categóricas: 4.
- Clima: **ok**.

## 4. Modelado

- LogisticRegression con `class_weight='balanced'`.
- RandomForest con `class_weight='balanced_subsample'`.
- HistGradientBoosting con `class_weight='balanced'`.
- Pipeline propio de imputación mediana, escalado estándar y one-hot con `handle_unknown='ignore'`.

| Modelo | PR-AUC LOSO | Brier LOSO | ROC-AUC LOSO | PR-AUC provincia | PR-AUC comuna |
|---|---|---|---|---|---|
| logistic_regression | 0.637 | 0.150 | 0.857 | 0.541 | 0.598 |
| random_forest | 0.635 | 0.113 | 0.860 | 0.571 | 0.654 |
| hist_gradient_boosting | 0.627 | 0.133 | 0.851 | 0.554 | 0.623 |

La diferencia de PR-AUC entre LogisticRegression y RandomForest es de 0.003 y ambos caen dentro de la banda de empate de 0.01. RandomForest se elige por su Brier marcadamente menor (0.113 vs 0.150) y su mejor desempeño espacial; no por un argmax ciego de una sola métrica.

### Baselines

| Baseline | PR-AUC LOSO | Brier LOSO | ROC-AUC LOSO | PR-AUC provincia | PR-AUC comuna |
|---|---|---|---|---|---|
| Prevalencia | 0.191 | 0.155 | 0.500 | 0.174 | 0.191 |
| Regla histórica | 0.537 | 0.123 | 0.830 | 0.506 | 0.560 |

## 5. Evaluación temporal (leave-one-season-out)

| Temporada | n test | positivos | PR-AUC | Brier | ROC-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| 2011_2012 | 560 | 136 | 0.676 | 0.133 | 0.818 | 0.887 | 0.346 | 0.497 |
| 2012_2013 | 560 | 148 | 0.721 | 0.127 | 0.859 | 0.745 | 0.514 | 0.608 |
| 2013_2014 | 560 | 131 | 0.681 | 0.132 | 0.858 | 0.577 | 0.626 | 0.601 |
| 2014_2015 | 560 | 127 | 0.786 | 0.104 | 0.898 | 0.693 | 0.748 | 0.720 |
| 2015_2016 | 560 | 114 | 0.766 | 0.096 | 0.910 | 0.681 | 0.675 | 0.678 |
| 2016_2017 | 560 | 124 | 0.704 | 0.114 | 0.880 | 0.653 | 0.653 | 0.653 |
| 2017_2018 | 560 | 121 | 0.744 | 0.112 | 0.881 | 0.635 | 0.719 | 0.674 |
| 2018_2019 | 560 | 130 | 0.712 | 0.115 | 0.872 | 0.648 | 0.608 | 0.627 |
| 2019_2020 | 560 | 107 | 0.640 | 0.113 | 0.872 | 0.576 | 0.636 | 0.604 |
| 2020_2021 | 560 | 55 | 0.525 | 0.116 | 0.852 | 0.328 | 0.691 | 0.444 |
| 2021_2022 | 560 | 59 | 0.375 | 0.110 | 0.841 | 0.370 | 0.627 | 0.465 |
| 2022_2023 | 560 | 59 | 0.452 | 0.094 | 0.853 | 0.354 | 0.475 | 0.406 |
| 2023_2024 | 560 | 91 | 0.611 | 0.096 | 0.858 | 0.654 | 0.374 | 0.476 |
| 2024_2025 | 560 | 98 | 0.501 | 0.124 | 0.789 | 0.536 | 0.459 | 0.495 |

La varianza entre folds es alta porque cada temporada tiene entre 56 y 149 zona-temporadas positivas y los incendios son episódicos. Los intervalos de confianza al 95% de los promedios están en `real_metrics.json`.

## 6. Validación espacial

Se evaluó leave-one-province-out y `StratifiedGroupKFold` por comuna. Sirve como prueba de estrés: el modelo no debe memorizar comunas. Los resultados espaciales son menores que LOSO, lo que confirma dependencia de historia local y de patrones específicos de zona.

| Modelo | PR-AUC provincia | Brier provincia | PR-AUC comuna | Brier comuna |
|---|---|---|---|---|
| logistic_regression | 0.541 | 0.198 | 0.598 | 0.196 |
| random_forest | 0.571 | 0.108 | 0.654 | 0.113 |
| hist_gradient_boosting | 0.554 | 0.121 | 0.623 | 0.134 |

## 7. Calibración

Método elegido: **sigmoid**. La calibración se evaluó de forma anidada: dentro de cada fold LOSO se ajustó `CalibratedClassifierCV` solo con temporadas de entrenamiento.

| Bin | Prob. media | Tasa observada | Gap absoluto | n |
|---|---|---|---|---|
| 1 | 0.038 | 0.014 | 0.024 | 784 |
| 2 | 0.042 | 0.006 | 0.035 | 784 |
| 3 | 0.047 | 0.033 | 0.014 | 784 |
| 4 | 0.056 | 0.056 | 0.000 | 784 |
| 5 | 0.068 | 0.087 | 0.019 | 784 |
| 6 | 0.091 | 0.133 | 0.042 | 784 |
| 7 | 0.134 | 0.162 | 0.028 | 784 |
| 8 | 0.222 | 0.256 | 0.034 | 784 |
| 9 | 0.429 | 0.449 | 0.020 | 784 |
| 10 | 0.732 | 0.717 | 0.015 | 784 |

ECE: **0.023**. Brier calibrado: **0.107**.

## 8. Umbrales operativos

| Punto | Umbral | Precision | Recall | F1 | Tasa predicha | TP/FP/FN/TN |
|---|---|---|---|---|---|---|
| 0.5 ciego | 0.500 | 0.673 | 0.436 | 0.529 | 0.124 | 654/318/846/6022 |
| F1 balanceado | 0.278 | 0.572 | 0.636 | 0.602 | 0.213 | 954/713/546/5627 |
| Alta precision (>=0.70) | 0.556 | 0.701 | 0.396 | 0.506 | 0.108 | 594/253/906/6087 |
| Alto recall (>=0.80) | 0.126 | 0.424 | 0.801 | 0.555 | 0.361 | 1202/1632/298/4708 |

Los umbrales no son argmax ciego: se derivan de la curva precision-recall out-of-fold y de objetivos explícitos de precision/recall. El punto `0.5 ciego` se incluye solo como referencia.

## 9. Importancia de variables

| Variable | Valor |
|---|---|
| prior_burn_rate | 0.0894 |
| prior_fire_area_last3_log | 0.0742 |
| seasons_since_last_fire | 0.0640 |
| prior_fires_last5_log | 0.0625 |
| prior_fires_last3_log | 0.0615 |
| prior_fire_area_total_log | 0.0475 |
| prior_fires_total_log | 0.0405 |
| prior_burned_seasons | 0.0344 |
| elev_mean_m | 0.0319 |
| centroid_lon | 0.0273 |
| prior_fires_last1_log | 0.0271 |
| area_km2 | 0.0270 |
| log_area_km2 | 0.0269 |
| comuna_prior_fire_rate_last1 | 0.0248 |
| centroid_lat | 0.0237 |

La importancia es descriptiva, no causal. Si el modelo elegido es un árbol, se reporta `feature_importances_`; si es logístico, coeficientes estandarizados.

## 10. Limitaciones y siguientes pasos

- No es un modelo operativo: es un baseline de investigación con cobertura espacial parcial.
- Las zonas cubren ~3.7% del área; los incendios fuera de zona no se etiquetan.
- No usa clima de la temporada objetivo, causas de ignición, caminos, líneas eléctricas ni capacidad de respuesta.
- Clima de la temporada previa desde NASA POWER (MERRA-2), centroide comunal (respaldo por límite de Open-Meteo); resolución de grilla gruesa en el centroide comunal, no microclima local.
- Los combustibles son un corte estático CONAF 2019; las plantaciones y el uso de suelo cambian.
- La selección del modelo y las métricas comparten folds; las métricas del elegido son optimistas.
- La validación espacial por provincia/comuna es un estrés de generalización, no una estimación de despliegue.
- El combustible/vegetación es un corte 2019 y la población es censo 2017; en temporadas previas son información futura, un supuesto estático fuerte.
- Próximo paso responsable: ampliar la capa de zonas a todo el territorio regional o etiquetar a nivel de celda H3, y agregar variables de ignición antrópica (caminos, tendido eléctrico, interfaces).
- Validar con una temporada completamente futura antes de cualquier uso operativo.

## 11. Artefactos

- `ml/real_model.joblib` (`sha256` `2b9f6d26782d6e7f...`).
- `real_dataset.csv`, `real_dataset_metadata.json`.
- `real_metrics.json`, `real_oof_predictions.csv`.
- `real_model_card.md`, `real_training_report.md`, `REAL_EDA.md`, `real_eda.json`.

## Reproducción

```bash
uv run python scripts/crispdm_real_model.py all
```

El comando anterior intenta Open-Meteo y, si hay límite 429, usa NASA POWER como respaldo; si ambos fallan, continúa sin clima y lo documenta.
