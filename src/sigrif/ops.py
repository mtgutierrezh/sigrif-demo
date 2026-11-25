"""Agregados operativos para el panel ejecutivo y la salud de servicios."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import settings
from .events import queue_depth
from .model_spec import FEATURE_LABELS, FEATURE_WEIGHTS, MODEL_VERSION
from .models import Alert, Evaluation, IngestionRun, Reading, Zone
from .monitoring import data_timestamps, freshness_minutes, risk_counts

logger = logging.getLogger(__name__)

MODEL_METADATA_PATH = Path(__file__).resolve().parents[2] / "ml" / "model_metadata.json"
STALE_AFTER_MINUTES = 45


@lru_cache(maxsize=1)
def predominant_variables() -> list[dict[str, Any]]:
    """Importancia del modelo cuando hay metadatos; si no, pesos documentados."""

    try:
        payload = json.loads(MODEL_METADATA_PATH.read_text(encoding="utf-8"))
        items = [
            {
                "feature": str(item["feature"]),
                "label": str(item.get("label", item["feature"])),
                "importance": round(float(item.get("importance", 0.0)), 4),
                "source": "modelo",
            }
            for item in payload.get("feature_importance", [])
            if isinstance(item, dict) and item.get("feature")
        ]
        if items:
            return sorted(items, key=lambda item: item["importance"], reverse=True)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.info("metadatos del modelo no disponibles; se usan pesos documentados")

    return sorted(
        (
            {
                "feature": feature,
                "label": FEATURE_LABELS.get(feature, feature),
                "importance": round(weight, 4),
                "source": "pesos_documentados",
            }
            for feature, weight in FEATURE_WEIGHTS.items()
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )


def _window_counts(session: Session, now: datetime) -> dict[str, int]:
    since = now - timedelta(hours=24)
    previous = now - timedelta(hours=48)
    evaluations_24h = (
        session.scalar(select(func.count(Evaluation.id)).where(Evaluation.created_at >= since)) or 0
    )
    evaluations_previous = (
        session.scalar(
            select(func.count(Evaluation.id)).where(
                Evaluation.created_at >= previous,
                Evaluation.created_at < since,
            )
        )
        or 0
    )
    alerts_24h = session.scalar(select(func.count(Alert.id)).where(Alert.created_at >= since)) or 0
    alerts_previous = (
        session.scalar(
            select(func.count(Alert.id)).where(
                Alert.created_at >= previous,
                Alert.created_at < since,
            )
        )
        or 0
    )
    return {
        "evaluations_24h": int(evaluations_24h),
        "evaluations_previous_24h": int(evaluations_previous),
        "evaluations_delta": int(evaluations_24h) - int(evaluations_previous),
        "alerts_24h": int(alerts_24h),
        "alerts_previous_24h": int(alerts_previous),
        "alerts_delta": int(alerts_24h) - int(alerts_previous),
    }


def _source_summary(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            Reading.source,
            func.count(Reading.id),
            func.max(func.coalesce(Reading.observed_at, Reading.created_at)),
        )
        .group_by(Reading.source)
        .order_by(func.count(Reading.id).desc())
    ).all()
    return [
        {
            "source": str(source),
            "readings": int(count),
            "last_at": last_at,
        }
        for source, count, last_at in rows
    ]


def build_executive_summary(session: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    counts = risk_counts(session)
    critical = session.scalars(
        select(Zone)
        .where(Zone.risk_level == "Alto")
        .order_by(Zone.risk_score.desc(), Zone.name)
        .limit(5)
    ).all()
    alerts_by_status = {
        str(status): int(count)
        for status, count in session.execute(
            select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
        )
    }
    active_alerts = sum(count for status, count in alerts_by_status.items() if status != "cerrada")
    return {
        "generated_at": now,
        "zones": sum(counts.values()),
        "risk_counts": counts,
        "critical_zones": critical,
        "active_alerts": active_alerts,
        "high_risk_zones": counts.get("Alto", 0),
        "alerts_by_status": alerts_by_status,
        "variation": _window_counts(session, now),
        "predominant_variables": predominant_variables(),
        "sources": _source_summary(session),
        "model_version": MODEL_VERSION,
    }


def check_ia_service() -> tuple[str, str]:
    try:
        response = httpx.get(f"{settings.ia_url.rstrip('/')}/health", timeout=2.0)
        response.raise_for_status()
        payload = response.json()
        version = payload.get("model_version") or MODEL_VERSION
        return "ok", f"Servicio de IA disponible · modelo {version}"
    except Exception:
        return "down", "Sin respuesta del servicio de inferencia"


def _postgis_status(session: Session) -> tuple[str, str]:
    try:
        version = session.scalar(text("SELECT PostGIS_Version()"))
    except Exception:
        return "down", "No se pudo consultar PostGIS"
    if not version:
        return "degraded", "La base de datos respondió sin versión de PostGIS"
    return "ok", f"PostGIS {version}"


def _ingestion_status(session: Session) -> tuple[str, str]:
    try:
        run = session.scalars(
            select(IngestionRun).order_by(IngestionRun.id.desc()).limit(1)
        ).first()
    except Exception:
        return "down", "No se pudo consultar el historial de ingesta"
    if run is None:
        return "sin_datos", "Sin ejecuciones de ingesta registradas"
    detail = (
        f"{run.provider}: {run.zones_ok}/{run.zones_total} zonas · "
        f"inicio {run.started_at.isoformat()}"
    )
    return ("ok" if run.status == "ok" else "degraded"), detail


def build_service_status(session: Session, *, p95_ms: float | None = None) -> dict[str, Any]:
    checked_at = datetime.now(UTC)
    services: list[dict[str, Any]] = [
        {
            "key": "api",
            "label": "API",
            "status": "ok",
            "detail": (
                f"FastAPI en línea · p95 {p95_ms:.0f} ms"
                if p95_ms is not None
                else "FastAPI en línea"
            ),
        }
    ]

    ia_status, ia_detail = check_ia_service()
    services.append({"key": "ia", "label": "IA", "status": ia_status, "detail": ia_detail})
    postgis_status, postgis_detail = _postgis_status(session)
    services.append(
        {
            "key": "postgis",
            "label": "PostGIS",
            "status": postgis_status,
            "detail": postgis_detail,
        }
    )

    depth: int | None = None
    if not settings.messaging_enabled:
        services.append(
            {
                "key": "sqs",
                "label": "SQS",
                "status": "disabled",
                "detail": "Mensajería asíncrona deshabilitada",
            }
        )
    else:
        depth = queue_depth()
        services.append(
            {
                "key": "sqs",
                "label": "SQS",
                "status": "ok" if depth is not None else "degraded",
                "detail": (
                    f"{depth} mensajes pendientes"
                    if depth is not None
                    else "No se pudo leer la profundidad de la cola"
                ),
            }
        )

    ingestion_status, ingestion_detail = _ingestion_status(session)
    services.append(
        {
            "key": "ingesta",
            "label": "Ingesta",
            "status": ingestion_status,
            "detail": ingestion_detail,
        }
    )

    try:
        last_ingest, _ = data_timestamps(session)
        freshness = freshness_minutes(last_ingest, checked_at)
    except Exception:
        last_ingest, freshness = None, None
    if freshness is None:
        freshness_status = "sin_datos"
        freshness_detail = "Sin lecturas registradas"
    else:
        freshness_status = "degraded" if freshness > STALE_AFTER_MINUTES else "ok"
        freshness_detail = f"{freshness:.0f} min desde la última lectura"
    services.append(
        {
            "key": "frescura",
            "label": "Frescura",
            "status": freshness_status,
            "detail": freshness_detail,
        }
    )

    statuses = {service["status"] for service in services}
    if "down" in statuses:
        overall = "down"
    elif "degraded" in statuses or "sin_datos" in statuses:
        overall = "degraded"
    else:
        overall = "ok"
    return {
        "checked_at": checked_at,
        "status": overall,
        "services": services,
        "queue_depth": depth,
        "last_ingest": last_ingest,
        "freshness_minutes": freshness,
        "stale": freshness is None or freshness > STALE_AFTER_MINUTES,
    }
