"""Notificaciones operativas por cambios de nivel y apertura de alertas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .model_spec import LABELS
from .models import Alert, Evaluation, Notification, Zone

LEVEL_CHANGE = "cambio_nivel"
ALERT_OPENED = "alerta_alto"
LEVEL_RANK = {level: index for index, level in enumerate(LABELS)}


def _now() -> datetime:
    return datetime.now(UTC)


def _actor(value: str | None) -> str:
    return value or "sistema"


def _exists(session: Session, evaluation_id: int | None, event_type: str) -> bool:
    if evaluation_id is None:
        return False
    return (
        session.scalar(
            select(Notification.id)
            .where(
                Notification.evaluation_id == evaluation_id,
                Notification.event_type == event_type,
            )
            .limit(1)
        )
        is not None
    )


def record_level_change(
    session: Session,
    zone: Zone,
    evaluation: Evaluation,
    previous_level: str | None,
    *,
    actor: str = "sistema",
) -> Notification | None:
    """Registra una notificación cuando cambia el nivel Bajo/Medio/Alto."""

    new_level = str(evaluation.risk_level)
    if previous_level not in LABELS or new_level not in LABELS or previous_level == new_level:
        return None
    if _exists(session, evaluation.id, LEVEL_CHANGE):
        return None

    direction = "sube" if LEVEL_RANK[new_level] > LEVEL_RANK[previous_level] else "baja"
    notification = Notification(
        zone_id=zone.id,
        evaluation_id=evaluation.id,
        event_type=LEVEL_CHANGE,
        level_from=previous_level,
        level_to=new_level,
        title=f"El nivel de riesgo {direction} de {previous_level} a {new_level}",
        detail=(
            f"{zone.name} ({zone.comuna}). Evaluación #{evaluation.id} con "
            f"P(Alto)={float(evaluation.risk_score):.2f}."
        ),
        actor=_actor(actor),
        created_at=_now(),
    )
    session.add(notification)
    return notification


def record_alert_opened(
    session: Session,
    zone: Zone,
    evaluation: Evaluation,
    alert: Alert,
    *,
    actor: str = "sistema",
) -> Notification | None:
    """Registra la apertura de una alerta Alto, sin duplicar la evaluación."""

    if _exists(session, evaluation.id, ALERT_OPENED):
        return None

    notification = Notification(
        zone_id=zone.id,
        alert_id=alert.id,
        evaluation_id=evaluation.id,
        event_type=ALERT_OPENED,
        level_from=None,
        level_to="Alto",
        title="Nueva alerta de nivel Alto",
        detail=(
            f"{zone.name} ({zone.comuna}). Alerta #{alert.id} asociada a la "
            f"evaluación #{evaluation.id} con P(Alto)={float(evaluation.risk_score):.2f}."
        ),
        actor=_actor(actor),
        created_at=_now(),
    )
    session.add(notification)
    return notification


def notification_payload(notification: Notification, zone: Zone | None) -> dict[str, Any]:
    """Resumen serializable, con los datos de zona usados por la interfaz."""

    return {
        "id": notification.id,
        "zone_id": notification.zone_id,
        "zone_name": zone.name if zone is not None else f"Zona {notification.zone_id}",
        "comuna": zone.comuna if zone is not None else "",
        "alert_id": notification.alert_id,
        "evaluation_id": notification.evaluation_id,
        "event_type": notification.event_type,
        "level_from": notification.level_from,
        "level_to": notification.level_to,
        "title": notification.title,
        "detail": notification.detail,
        "actor": notification.actor,
        "created_at": notification.created_at,
        "read_at": notification.read_at,
        "read_by": notification.read_by,
    }
