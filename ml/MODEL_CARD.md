# Model card · Clasificador de riesgo sectorial SIGRIF

## Identificación

| Campo | Valor |
|---|---|
| Versión | `random-forest-0.2.0` |
| Tipo | `RandomForestClassifier` de scikit-learn |
| Artefacto | `artifacts/risk_model.joblib` |
| Entrenado | 2026-11-04 |
| Semilla | 42 |
| Dataset | `data/training/sigrif_risk_synthetic.csv` |
| Hash del dataset | `48da94a8e80d7fb0aaeced3f1b60f9bafa9f042e06b33e66b8969cb6662a7fdf` |

## Uso previsto

El modelo estima una probabilidad de riesgo `Alto` para un sector y la traduce
en uno de tres niveles: `Bajo`, `Medio` o `Alto`. La API pública agrega
explicabilidad local y un motor de prescripción operativa. Está pensado como
apoyo académico para priorizar patrullaje, revisión de combustibles y
coordinación preventiva.

No debe usarse para predecir la fecha, hora o ubicación exacta de un incendio,
para reemplazar decisiones de CONAF o SENAPRED, ni para emitir alertas públicas
sin revisión humana.

## Datos y entrenamiento

| Aspecto | Decisión |
|---|---|
| Variables | Temperatura, humedad, viento, vegetación, incendios históricos y pendiente. |
| Muestras | 3000, generadas con semilla 42. |
| Partición | 80 % entrenamiento (2400) y 20 % prueba (600), estratificada. |
| Hiperparámetros | 160 árboles, `max_depth=10`, `min_samples_leaf=3`, `class_weight="balanced"`. |
| Validación | 5-fold sobre el conjunto de entrenamiento, métrica F1 macro. |
| Registro | Joblib + `model_metadata.json` + `metrics.json`; sin MLflow. |

## Métricas de la ejecución vigente

| Métrica | Valor |
|---|---|
| Accuracy | 0.8750 |
| F1 macro | 0.8644 |
| F1 ponderado | 0.8761 |
| ROC-AUC OVR | 0.9729 |
| F1 macro en 5-fold | 0.8760 ± 0.0124 |

| Clase | Precisión | Recall | F1 | Soporte en prueba |
|---|---|---|---|---|
| Bajo | 0.8480 | 0.9138 | 0.8797 | 116 |
| Medio | 0.9263 | 0.8626 | 0.8933 | 364 |
| Alto | 0.7721 | 0.8750 | 0.8203 | 120 |

Matriz de confusión (filas reales, columnas predichas):

```text
          Bajo  Medio  Alto
Bajo       106     10     0
Medio       19    314    31
Alto         0     15   105
```

La clase `Alto` tiene la precisión más baja: 31 casos `Medio` se clasificaron
como `Alto`. Para un sistema de alerta temprana preferimos ese comportamiento
antes que omitir un riesgo alto, pero el umbral debe calibrarse con datos
reales antes de operar.

## Importancia de variables

| Variable | Importancia |
|---|---|
| Temperatura | 0.3705 |
| Humedad relativa | 0.1647 |
| Vegetación combustible | 0.1498 |
| Velocidad del viento | 0.1493 |
| Pendiente | 0.0891 |
| Incendios históricos | 0.0766 |

La importancia global se complementa con una sensibilidad local: para cada
consulta se reemplaza una variable por un valor de bajo riesgo y se mide cuánto
baja la probabilidad de `Alto`. Así se explican los tres factores principales
sin afirmar causalidad.

## Escenario de gestión

Para cada evaluación se calcula un contrafactual simple: si la vegetación
combustible baja 0.20, ¿cómo cambia la probabilidad de riesgo alto? Es una
palanca accionable y acotada. No se generan escenarios sobre temperatura,
humedad o viento porque el equipo no puede modificarlos.

## Límites y riesgos

- Las etiquetas son académicas; las métricas validan la regla de etiquetado, no
  el desempeño real en la Región de Valparaíso.
- El modelo no está calibrado con incendios reales por sector.
- La muestra sintética puede sobrerrepresentar la clase `Medio`.
- Las predicciones deben presentarse como estimaciones, no como certezas.
- La prescripción es un motor de reglas; requiere validación con operadores y
  organismos competentes.
- Si el servicio de IA falla, la API responde `503` y no inventa una predicción.

## Reproducción y actualización

```bash
make train
```

El reentrenamiento previsto es trimestral o cuando cambie la distribución de
las variables. La promoción de una nueva versión es manual: se revisan las
métricas, se publica el artefacto y se actualiza la referencia de despliegue.
