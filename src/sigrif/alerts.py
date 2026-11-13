"""Gestión operativa de alertas por zona.

Una zona mantiene a lo más una alerta abierta. Las evaluaciones sucesivas se
registran como eventos de reclasificación, de modo que el historial conserve
la trazabilidad sin duplicar alertas.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alert, AlertEvent, Evaluation, Zone

ALERT_STATUSES = ("nueva", "en_revision", "cerrada")


def _now() -> datetime:
    return datetime.now(UTC)


def _actor(value: str | None) -> str:
    return value or "sistema"


def add_event(
    session: Session,
    alert: Alert,
    event_type: str,
    *,
    detail: str | None = None,
    actor: str = "sistema",
) -> AlertEvent:
    """Agrega un evento al historial de la alerta sin confirmar la transacción."""

    event = AlertEvent(
        alert_id=alert.id,
        event_type=event_type,
        detail=detail,
        actor=_actor(actor),
        created_at=_now(),
    )
    session.add(event)
    alert.updated_at = _now()
    return event


def ensure_alert(session: Session, zone: Zone, evaluation: Evaluation) -> Alert:
    """Abre una alerta para la zona o registra una reclasificación.

    Solo se crea una alerta nueva cuando no existe otra abierta. Si ya hay una
    en curso, se actualiza su evaluación de referencia y se agrega el evento
    ``reclasificada`` con el nuevo nivel y score.
    """

    alert = session.scalar(
        select(Alert)
        .where(Alert.zone_id == zone.id, Alert.status != "cerrada")
        .order_by(Alert.id.desc())
        .limit(1)
    )
    detail = (
        f"Evaluación #{evaluation.id}: nivel {evaluation.risk_level} "
        f"con score {evaluation.risk_score:.2f}."
    )
    actor = _actor(getattr(evaluation, "created_by", None))

    if alert is not None:
        alert.evaluation_id = evaluation.id
        alert.updated_at = _now()
        add_event(session, alert, "reclasificada", detail=detail, actor=actor)
        return alert

    alert = Alert(
        zone_id=zone.id,
        evaluation_id=evaluation.id,
        status="nueva",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(alert)
    session.flush()
    add_event(session, alert, "creada", detail=detail, actor=actor)
    return alert


def update_alert(
    session: Session,
    alert: Alert,
    *,
    status: str | None = None,
    assigned_to: str | None = None,
    comment: str | None = None,
    actor: str,
) -> Alert:
    """Aplica cambios de estado, responsable o comentario y deja historial."""

    if status is not None and status not in ALERT_STATUSES:
        raise ValueError(f"Estado de alerta inválido: {status}")

    changed = False
    now = _now()

    if status is not None and status != alert.status:
        previous = alert.status
        alert.status = status
        if status == "cerrada":
            alert.closed_at = now
        elif alert.closed_at is not None:
            alert.closed_at = None
        add_event(
            session,
            alert,
            "estado",
            detail=f"{previous} -> {status}",
            actor=actor,
        )
        changed = True

    if assigned_to is not None:
        new_assigned = assigned_to.strip() or None
        if new_assigned != alert.assigned_to:
            previous = alert.assigned_to or "sin asignar"
            alert.assigned_to = new_assigned
            add_event(
                session,
                alert,
                "asignacion",
                detail=f"{previous} -> {new_assigned or 'sin asignar'}",
                actor=actor,
            )
            changed = True

    if comment is not None:
        new_comment = comment.strip() or None
        if new_comment != alert.comment:
            alert.comment = new_comment
            add_event(
                session,
                alert,
                "comentario",
                detail=new_comment or "Comentario eliminado.",
                actor=actor,
            )
            changed = True

    if changed:
        alert.updated_at = now

    return alert
