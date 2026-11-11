"""Métricas operativas y deriva de datos para SIGRIF."""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from prometheus_client import Gauge
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .events import queue_depth
from .model_spec import FEATURES
from .models import Reading, Zone

BASELINE_PATH = Path(__file__).parent / "data" / "drift_baseline.json"
DRIFT_WINDOW = 200
MIN_DRIFT_SAMPLES = 30

ZONES_TOTAL = Gauge("sigrif_zones_total", "Zonas monitoreadas")
ZONES_BY_RISK = Gauge("sigrif_zones_by_risk", "Zonas por nivel de riesgo", ["level"])
FRESHNESS = Gauge("sigrif_data_freshness_minutes", "Minutos desde la última lectura")
ACTIVE_ALERTS = Gauge("sigrif_active_alerts", "Zonas actualmente en riesgo Alto")
QUEUE_DEPTH = Gauge("sigrif_queue_depth", "Mensajes pendientes en la cola de ingesta")
DRIFT_PSI = Gauge("sigrif_drift_psi", "Índice de estabilidad poblacional por variable", ["feature"])


@lru_cache(maxsize=1)
def load_baseline() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _bin_index(value: float, bins: list[float]) -> int:
    if len(bins) < 2:
        return 0
    index = bisect_right(bins, value) - 1
    return max(0, min(index, len(bins) - 2))


def population_stability_index(
    values: list[float],
    bins: list[float],
    expected: list[float],
) -> float:
    """PSI con corrección por proporciones vacías (evita log(0))."""

    if not values or len(bins) < 2 or len(expected) != len(bins) - 1:
        return 0.0
    counts = [0] * (len(bins) - 1)
    for value in values:
        counts[_bin_index(float(value), bins)] += 1
    total = len(values)
    psi = 0.0
    for count, expected_share in zip(counts, expected, strict=True):
        actual = max(count / total, 1e-6)
        reference = max(float(expected_share), 1e-6)
        psi += (actual - reference) * math.log(actual / reference)
    return round(psi, 4)


def _status(psi: float, samples: int) -> str:
    if samples < MIN_DRIFT_SAMPLES:
        return "insuficiente"
    if psi >= 0.25:
        return "deriva"
    if psi >= 0.1:
        return "moderada"
    return "estable"


def drift_report(session: Session) -> list[dict[str, Any]]:
    baseline = load_baseline()
    if not baseline:
        return []
    readings = session.scalars(
        select(Reading).order_by(Reading.id.desc()).limit(DRIFT_WINDOW)
    ).all()
    result: list[dict[str, Any]] = []
    for feature in FEATURES:
        reference = baseline.get(feature, {})
        values = [float(getattr(reading, feature)) for reading in readings]
        psi = population_stability_index(
            values,
            [float(value) for value in reference.get("bins", [])],
            [float(value) for value in reference.get("proportions", [])],
        )
        current_mean = round(sum(values) / len(values), 4) if values else 0.0
        result.append(
            {
                "feature": feature,
                "psi": psi,
                "status": _status(psi, len(values)),
                "baseline_mean": float(reference.get("mean", 0.0)),
                "current_mean": current_mean,
                "samples": len(values),
            }
        )
    return result


def data_timestamps(session: Session) -> tuple[datetime | None, str | None]:
    last = session.scalar(select(func.max(func.coalesce(Reading.observed_at, Reading.created_at))))
    source = session.scalar(select(Reading.source).order_by(Reading.id.desc()).limit(1))
    return last, source


def freshness_minutes(last: datetime | None, now: datetime | None = None) -> float | None:
    if last is None:
        return None
    reference = now or datetime.now(UTC)
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return round(max(0.0, (reference - last).total_seconds() / 60), 1)


def risk_counts(session: Session) -> dict[str, int]:
    rows = session.execute(select(Zone.risk_level, func.count(Zone.id)).group_by(Zone.risk_level))
    counts = {"Bajo": 0, "Medio": 0, "Alto": 0}
    for level, count in rows:
        counts[str(level)] = int(count)
    return counts


def refresh_metrics(session: Session) -> None:
    counts = risk_counts(session)
    ZONES_TOTAL.set(sum(counts.values()))
    for level, count in counts.items():
        ZONES_BY_RISK.labels(level).set(count)
    last, _ = data_timestamps(session)
    freshness = freshness_minutes(last)
    FRESHNESS.set(freshness if freshness is not None else -1)
    ACTIVE_ALERTS.set(counts.get("Alto", 0))
    depth = queue_depth()
    QUEUE_DEPTH.set(depth if depth is not None else -1)
    for item in drift_report(session):
        DRIFT_PSI.labels(str(item["feature"])).set(float(item["psi"]))
