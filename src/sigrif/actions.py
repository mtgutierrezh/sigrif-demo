"""Ciclo de vida de acciones preventivas e incidentes operativos."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import PreventiveAction

ACTION_KINDS = ("accion", "incidente")
ACTION_STATUSES = ("pendiente", "en_ejecucion", "completada", "cancelada")
ACTION_PRIORITIES = ("baja", "media", "alta")
CLOSED_STATUSES = {"completada", "cancelada"}
OPEN_STATUSES = {"pendiente", "en_ejecucion"}
ALLOWED_UPDATE_FIELDS = {"status", "assigned_to", "detail", "due_date", "priority"}


def _now() -> datetime:
    return datetime.now(UTC)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def is_overdue(action: PreventiveAction, today: date | None = None) -> bool:
    if action.due_date is None or action.status in CLOSED_STATUSES:
        return False
    return action.due_date < (today or datetime.now(UTC).date())


def update_action(
    action: PreventiveAction,
    changes: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> PreventiveAction:
    """Aplica solo los campos enviados y mantiene ``closed_at`` consistente."""

    unknown = set(changes) - ALLOWED_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"Campos no permitidos: {', '.join(sorted(unknown))}")

    timestamp = now or _now()
    changed = False

    if "status" in changes:
        status = str(changes["status"])
        if status not in ACTION_STATUSES:
            raise ValueError(f"Estado de acción inválido: {status}")
        if status != action.status:
            action.status = status
            if status in CLOSED_STATUSES:
                action.closed_at = timestamp
            else:
                action.closed_at = None
            changed = True

    if "priority" in changes:
        priority = str(changes["priority"])
        if priority not in ACTION_PRIORITIES:
            raise ValueError(f"Prioridad inválida: {priority}")
        if priority != action.priority:
            action.priority = priority
            changed = True

    if "assigned_to" in changes:
        assigned_to = _clean(changes["assigned_to"])
        if assigned_to != action.assigned_to:
            action.assigned_to = assigned_to
            changed = True

    if "detail" in changes:
        detail = _clean(changes["detail"])
        if detail != action.detail:
            action.detail = detail
            changed = True

    if "due_date" in changes:
        due_date = changes["due_date"]
        if due_date is not None and not isinstance(due_date, date):
            raise ValueError("La fecha de vencimiento debe ser una fecha")
        if due_date != action.due_date:
            action.due_date = due_date
            changed = True

    if changed:
        action.updated_at = timestamp

    return action


def build_action_summary(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(PreventiveAction.status, func.count(PreventiveAction.id)).group_by(
            PreventiveAction.status
        )
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    today = datetime.now(UTC).date()
    overdue = (
        session.scalar(
            select(func.count(PreventiveAction.id)).where(
                PreventiveAction.due_date.is_not(None),
                PreventiveAction.due_date < today,
                PreventiveAction.status.notin_(CLOSED_STATUSES),
            )
        )
        or 0
    )
    open_incidents = (
        session.scalar(
            select(func.count(PreventiveAction.id)).where(
                PreventiveAction.kind == "incidente",
                PreventiveAction.status.in_(OPEN_STATUSES),
            )
        )
        or 0
    )
    return {
        "total": sum(counts.values()),
        "pendiente": counts.get("pendiente", 0),
        "en_ejecucion": counts.get("en_ejecucion", 0),
        "completada": counts.get("completada", 0),
        "cancelada": counts.get("cancelada", 0),
        "overdue": int(overdue),
        "open_incidents": int(open_incidents),
    }
