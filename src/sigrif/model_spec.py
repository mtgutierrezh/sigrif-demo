"""Especificación compartida del modelo de riesgo de SIGRIF.

Este módulo no entrena ni carga modelos: solo define las variables, sus rangos,
la regla académica que genera las etiquetas sintéticas y utilidades para
construir la matriz de entrenamiento. Separar esta especificación permite que
el script de entrenamiento y el servicio de inferencia usen exactamente las
mismas columnas y el mismo orden.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

FEATURES: tuple[str, ...] = (
    "temperature",
    "humidity",
    "wind_speed",
    "vegetation",
    "historical_fires",
    "slope",
)

LABELS: tuple[str, ...] = ("Bajo", "Medio", "Alto")
LABEL_TO_INDEX: dict[str, int] = {label: index for index, label in enumerate(LABELS)}

FEATURE_LABELS: dict[str, str] = {
    "temperature": "Temperatura",
    "humidity": "Humedad relativa",
    "wind_speed": "Velocidad del viento",
    "vegetation": "Vegetación combustible",
    "historical_fires": "Incendios históricos",
    "slope": "Pendiente",
}

FEATURE_UNITS: dict[str, str] = {
    "temperature": "°C",
    "humidity": "%",
    "wind_speed": "km/h",
    "vegetation": "0–1",
    "historical_fires": "eventos",
    "slope": "°",
}

FEATURE_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (-10.0, 50.0),
    "humidity": (0.0, 100.0),
    "wind_speed": (0.0, 150.0),
    "vegetation": (0.0, 1.0),
    "historical_fires": (0.0, 30.0),
    "slope": (0.0, 60.0),
}

LOW_RISK_BASELINES: dict[str, float] = {
    "temperature": 10.0,
    "humidity": 85.0,
    "wind_speed": 5.0,
    "vegetation": 0.05,
    "historical_fires": 0.0,
    "slope": 5.0,
}

DEFAULT_SEED = 42
DEFAULT_DATASET_SIZE = 3000
ALTO_THRESHOLD = 0.62
MEDIO_THRESHOLD = 0.42
MODEL_VERSION = "random-forest-0.2.0"

FEATURE_WEIGHTS: dict[str, float] = {
    "temperature": 0.30,
    "humidity": 0.20,
    "wind_speed": 0.15,
    "vegetation": 0.15,
    "historical_fires": 0.10,
    "slope": 0.10,
}


def _rule_score(row: Mapping[str, float]) -> float:
    return (
        FEATURE_WEIGHTS["temperature"] * (row["temperature"] / 40.0)
        + FEATURE_WEIGHTS["humidity"] * (1.0 - row["humidity"] / 100.0)
        + FEATURE_WEIGHTS["wind_speed"] * (row["wind_speed"] / 80.0)
        + FEATURE_WEIGHTS["vegetation"] * row["vegetation"]
        + FEATURE_WEIGHTS["historical_fires"] * (row["historical_fires"] / 15.0)
        + FEATURE_WEIGHTS["slope"] * (row["slope"] / 45.0)
    )


def synthetic_rows(
    size: int = DEFAULT_DATASET_SIZE,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    """Genera filas sintéticas con las seis variables y su etiqueta académica."""

    rng = np.random.default_rng(seed)
    temperature = rng.uniform(5.0, 40.0, size)
    humidity = rng.uniform(10.0, 90.0, size)
    wind_speed = rng.uniform(0.0, 80.0, size)
    vegetation = rng.uniform(0.0, 1.0, size)
    historical_fires = rng.integers(0, 16, size)
    slope = rng.uniform(0.0, 45.0, size)

    rows: list[dict[str, Any]] = []
    for index in range(size):
        row: dict[str, Any] = {
            "sample_id": index + 1,
            "temperature": round(float(temperature[index]), 2),
            "humidity": round(float(humidity[index]), 2),
            "wind_speed": round(float(wind_speed[index]), 2),
            "vegetation": round(float(vegetation[index]), 4),
            "historical_fires": int(historical_fires[index]),
            "slope": round(float(slope[index]), 2),
        }
        score = _rule_score(row)
        row["rule_score"] = round(score, 4)
        row["risk_level"] = (
            "Alto" if score > ALTO_THRESHOLD else "Medio" if score > MEDIO_THRESHOLD else "Bajo"
        )
        rows.append(row)
    return rows


def features_from_row(row: Mapping[str, Any]) -> dict[str, float]:
    """Extrae solo las variables del modelo, en el orden esperado."""

    return {feature: float(row[feature]) for feature in FEATURES}


def feature_vector(values: Mapping[str, Any] | Sequence[Any]) -> list[float]:
    """Convierte un mapeo o una secuencia en el vector ordenado del modelo."""

    if isinstance(values, Mapping):
        return [float(values[feature]) for feature in FEATURES]
    if len(values) != len(FEATURES):
        raise ValueError(f"Se esperaban {len(FEATURES)} variables y llegaron {len(values)}")
    return [float(value) for value in values]


def dataset_matrix(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve ``X`` e ``y`` listos para scikit-learn."""

    materialized = list(rows)
    features = np.array(
        [[float(row[feature]) for feature in FEATURES] for row in materialized],
        dtype=float,
    )
    labels = np.array([LABEL_TO_INDEX[str(row["risk_level"])] for row in materialized], dtype=int)
    return features, labels
