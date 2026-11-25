"""Índice de prioridad operativa explicable para las zonas monitoreadas.

El índice ordena la revisión territorial, no reemplaza el nivel de riesgo del
modelo. La densidad usa la población oficial de los sectores municipales de
Valparaíso y el área geográfica calculada por PostGIS en hectáreas.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_ZONES_PATH = (
    ROOT / "src" / "sigrif" / "data" / ("cerros_sectores_valparaiso_region_oficial.geojson")
)

PRIORITY_WEIGHTS = {
    "alto_probability": 0.45,
    "vegetation": 0.20,
    "historical_fires": 0.15,
    "slope": 0.10,
    "population_density": 0.10,
}
COMPONENT_LABELS = {
    "alto_probability": "P(Alto)",
    "vegetation": "Vegetación",
    "historical_fires": "Incendios históricos",
    "slope": "Pendiente",
    "population_density": "Densidad de población",
}
PRIORITY_THRESHOLDS = {"alta": 60.0, "media": 35.0}
METHODOLOGY_NOTE = (
    "El índice ordena la revisión operativa y no reemplaza el nivel de riesgo del modelo. "
    "Todavía no incorpora viviendas, colegios ni infraestructura expuesta. "
    "La densidad usa población municipal y área geográfica PostGIS; normaliza con log1p "
    "y el percentil 95 para reducir el efecto de outliers."
)


def _as_population(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        population = float(value)
    except (TypeError, ValueError):
        return None
    if population <= 0:
        return None
    return population


@lru_cache(maxsize=1)
def official_population_by_name() -> dict[str, float]:
    """Población oficial por nombre de zona, cargada una sola vez desde el geojson."""

    payload = json.loads(OFFICIAL_ZONES_PATH.read_text(encoding="utf-8"))
    population: dict[str, float] = {}
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        name = str(properties.get("name") or "").strip()
        value = _as_population(properties.get("Población"))
        if name and value is not None:
            population[name] = value
    return population


def percentile(values: Sequence[float], fraction: float) -> float:
    """Percentil con interpolación lineal; 0 si no hay datos."""

    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def density_per_hectare(population: float | None, area_ha: float | None) -> float | None:
    """Densidad en habitantes por hectárea; None si falta población o área válida."""

    if population is None or area_ha is None or area_ha <= 0:
        return None
    return population / area_ha


def priority_level(score: float) -> str:
    if score >= PRIORITY_THRESHOLDS["alta"]:
        return "Alta"
    if score >= PRIORITY_THRESHOLDS["media"]:
        return "Media"
    return "Baja"


def _effective_weights(density_available: bool) -> dict[str, float]:
    weights = dict(PRIORITY_WEIGHTS)
    if density_available:
        return weights
    remaining = {key: value for key, value in weights.items() if key != "population_density"}
    total = sum(remaining.values())
    return {key: value / total for key, value in remaining.items()}


def _component(
    key: str,
    *,
    value: float | None,
    normalized: float | None,
    weight: float,
) -> dict[str, Any]:
    contribution = 0.0 if normalized is None else normalized * weight
    return {
        "key": key,
        "label": COMPONENT_LABELS[key],
        "value": None if value is None else round(value, 4),
        "normalized": None if normalized is None else round(normalized, 4),
        "weight": round(weight, 4),
        "contribution": round(contribution, 4),
    }


def build_priority_ranking(
    zones: Sequence[Any],
    area_ha_by_zone: Mapping[int, float | None],
    population_by_name: Mapping[str, float],
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Construye el ranking con componentes, cobertura y metadatos del índice."""

    fires = [max(float(zone.historical_fires or 0), 0.0) for zone in zones]
    fires_p95 = percentile(fires, 0.95)
    if fires_p95 <= 0:
        fires_p95 = max(fires, default=0.0)
    fires_denominator = fires_p95 if fires_p95 > 0 else 1.0

    rows: list[dict[str, Any]] = []
    density_logs: list[float] = []
    known_population = 0

    for zone in zones:
        population = _as_population(population_by_name.get(zone.name))
        if population is not None:
            known_population += 1
        area_ha = area_ha_by_zone.get(zone.id)
        density = density_per_hectare(population, area_ha)
        if density is not None:
            density_logs.append(math.log1p(max(density, 0.0)))
        rows.append(
            {
                "zone": zone,
                "population": population,
                "area_ha": area_ha,
                "density": density,
            }
        )

    density_p95_log = percentile(density_logs, 0.95)
    if density_p95_log <= 0:
        density_p95_log = max(density_logs, default=0.0)
    density_denominator = density_p95_log if density_p95_log > 0 else 1.0

    for row in rows:
        zone = row["zone"]
        density = row["density"]
        density_available = density is not None
        weights = _effective_weights(density_available)
        components = [
            _component(
                "alto_probability",
                value=float(zone.risk_score or 0.0),
                normalized=min(max(float(zone.risk_score or 0.0), 0.0), 1.0),
                weight=weights["alto_probability"],
            ),
            _component(
                "vegetation",
                value=float(zone.vegetation or 0.0),
                normalized=min(max(float(zone.vegetation or 0.0), 0.0), 1.0),
                weight=weights["vegetation"],
            ),
            _component(
                "historical_fires",
                value=float(zone.historical_fires or 0.0),
                normalized=min(
                    max(float(zone.historical_fires or 0.0) / fires_denominator, 0.0),
                    1.0,
                ),
                weight=weights["historical_fires"],
            ),
            _component(
                "slope",
                value=float(zone.slope or 0.0),
                normalized=min(max(float(zone.slope or 0.0) / 60.0, 0.0), 1.0),
                weight=weights["slope"],
            ),
        ]
        if density_available:
            normalized_density = min(
                max(math.log1p(max(density, 0.0)) / density_denominator, 0.0), 1.0
            )
            components.append(
                _component(
                    "population_density",
                    value=density,
                    normalized=normalized_density,
                    weight=weights["population_density"],
                )
            )
        else:
            components.append(
                _component(
                    "population_density",
                    value=None,
                    normalized=None,
                    weight=0.0,
                )
            )

        weighted = sum(
            (component["normalized"] or 0.0) * component["weight"] for component in components
        )
        score = round(weighted * 100, 1)
        row["score"] = min(max(score, 0.0), 100.0)
        row["components"] = components

    rows.sort(key=lambda item: (-item["score"], item["zone"].id))
    ranking = rows[: max(1, limit)]
    items = [
        {
            "position": position,
            "zone_id": row["zone"].id,
            "zone_name": row["zone"].name,
            "comuna": row["zone"].comuna,
            "risk_level": row["zone"].risk_level,
            "priority_level": priority_level(row["score"]),
            "alto_probability": round(float(row["zone"].risk_score or 0.0), 4),
            "historical_fires": int(row["zone"].historical_fires or 0),
            "population": row["population"],
            "population_available": row["population"] is not None,
            "density_available": row["density"] is not None,
            "population_density": (None if row["density"] is None else round(row["density"], 2)),
            "area_ha": None if row["area_ha"] is None else round(row["area_ha"], 2),
            "score": row["score"],
            "components": row["components"],
        }
        for position, row in enumerate(ranking, start=1)
    ]

    return {
        "generated_at": datetime.now(UTC),
        "limit": limit,
        "total_zones": len(zones),
        "population_coverage": {"known": known_population, "total": len(zones)},
        "weights": dict(PRIORITY_WEIGHTS),
        "fires_p95": round(fires_p95, 4),
        "density_p95_log": round(density_p95_log, 4),
        "thresholds": dict(PRIORITY_THRESHOLDS),
        "methodology_note": METHODOLOGY_NOTE,
        "items": items,
    }
