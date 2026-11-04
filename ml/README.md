# Modelo de riesgo SIGRIF

Esta carpeta reúne los artefactos y la documentación del clasificador de riesgo
sectorial. El modelo es un Random Forest de scikit-learn que trabaja solo con
CPU y seis variables: temperatura, humedad relativa, velocidad del viento,
vegetación combustible, incendios históricos y pendiente.

## Archivos

| Archivo | Contenido |
|---|---|
| `model_metadata.json` | Versión, variables, semilla, hash del dataset, hiperparámetros, métricas e importancia de variables. |
| `metrics.json` | Métricas de la última ejecución de entrenamiento. |
| `../data/training/sigrif_risk_synthetic.csv` | Dataset sintético académico usado para entrenar y evaluar. |
| `../artifacts/risk_model.joblib` | Artefacto serializado; se genera localmente y no se versiona. |
| `DATASET_CARD.md` | Origen, variables, regla de etiquetado y límites del dataset. |
| `MODEL_CARD.md` | Uso previsto, métricas, explicabilidad y límites del modelo. |

## Reproducir el entrenamiento

Desde la raíz del repositorio:

```bash
make train
```

El comando equivalente es:

```bash
uv run python scripts/train_model.py --cross-validate
```

El script escribe el dataset en `data/training/`, el artefacto en `artifacts/` y
los metadatos y métricas en `ml/`. La semilla por defecto es 42 y el tamaño de
muestra es 3000. Para una ejecución rápida sin validación cruzada:

```bash
make train-fast
```

## Versionado y despliegue

La versión vigente es `random-forest-0.2.0`. El servicio de IA carga el
artefacto indicado por `SIGRIF_MODEL_PATH`; si no existe y se configuró
`SIGRIF_MODEL_S3_URI`, lo descarga desde S3. En producción no se entrena al
iniciar: el artefacto se genera en el pipeline de entrenamiento, se evalúa y se
publica de forma explícita.

Para publicar el artefacto en el bucket del despliegue:

```bash
make publish-model BUCKET=sigrif-prod-...
```

El script sube `risk_model.joblib`, `model_metadata.json` y `metrics.json` al
prefijo `models/`. El servidor los descarga en cada despliegue.

## Límites

Las etiquetas se construyeron con una regla académica ponderada, no con
observaciones oficiales de incendios por sector. Por eso las métricas validan
que el modelo aprendió esa regla, no que prediga el riesgo real. La comparación
con datos de CONAF, DMC y otras fuentes queda como trabajo de validación
posterior.
