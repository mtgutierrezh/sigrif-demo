from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .events import publish_alert
from .models import Evaluation, Reading, Zone
from .prescription import build_prescription


def _as_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def store_evaluation(
    session: Session,
    zone: Zone,
    features: dict[str, Any],
    prediction: dict[str, Any],
    *,
    source: str = "manual",
    observed_at: datetime | str | None = None,
    request_id: str | None = None,
    created_by: str = "local",
    prescription_actions: list[dict[str, Any]] | None = None,
) -> Evaluation:
    """Persiste lectura, evaluación y alerta de forma consistente.

    La evaluación es idempotente cuando llega con ``observed_at``: si la
    lectura ya existe, se reutiliza y no se duplica la alerta. Esto importa
    porque SQS entrega al menos una vez.
    """

    observed = _as_datetime(observed_at)
    evaluated_at = datetime.now(UTC)
    risk_level = str(prediction.get("risk_level", ""))
    risk_score = float(prediction.get("risk_score", 0.0))

    reading: Reading | None = None
    if observed is not None:
        reading = session.scalar(
            select(Reading).where(
                Reading.zone_id == zone.id,
                Reading.observed_at == observed,
            )
        )
        if reading is not None:
            existing = session.scalar(
                select(Evaluation)
                .where(Evaluation.reading_id == reading.id)
                .order_by(Evaluation.id.desc())
                .limit(1)
            )
            if existing is not None:
                return existing

    if reading is None:
        reading = Reading(
            zone_id=zone.id,
            temperature=float(features["temperature"]),
            humidity=float(features["humidity"]),
            wind_speed=float(features["wind_speed"]),
            vegetation=float(features["vegetation"]),
            historical_fires=int(features.get("historical_fires", 0)),
            slope=float(features["slope"]),
            risk_level=risk_level,
            risk_score=risk_score,
            source=source,
            observed_at=observed,
            created_at=evaluated_at,
        )
        session.add(reading)
        session.flush()

    prescription = prescription_actions
    if prescription is None:
        prescription = build_prescription(features, prediction)

    evaluation = Evaluation(
        zone_id=zone.id,
        reading_id=reading.id,
        risk_level=risk_level,
        risk_score=risk_score,
        model_version=str(prediction.get("model_version", "unknown")),
        features=features,
        probabilities=prediction.get("probabilities", {}),
        factors=prediction.get("factors", []),
        scenario=prediction.get("scenario"),
        prescription=prescription,
        source=source,
        request_id=request_id,
        created_by=created_by,
        created_at=evaluated_at,
    )
    session.add(evaluation)

    zone.risk_level = risk_level
    zone.risk_score = risk_score
    zone.last_source = source

    if risk_level == "Alto":
        cooldown = timedelta(hours=max(1, settings.alert_cooldown_hours))
        if zone.last_alert_at is None or zone.last_alert_at < evaluated_at - cooldown:
            delivered = publish_alert(
                {
                    "zone_id": zone.id,
                    "zone": zone.name,
                    "comuna": zone.comuna,
                    "risk_level": risk_level,
                    "risk_score": round(risk_score, 4),
                    "source": source,
                    "observed_at": (observed or evaluated_at).isoformat(),
                    "actions": [
                        {
                            "code": action.get("code"),
                            "title": action.get("title"),
                            "priority": action.get("priority"),
                        }
                        for action in prescription[:3]
                    ],
                }
            )
            if delivered:
                zone.last_alert_at = evaluated_at

    session.commit()
    session.refresh(evaluation)
    return evaluation


def evaluate_and_store(
    session: Session,
    zone: Zone,
    features: dict[str, Any],
    *,
    source: str = "manual",
    observed_at: datetime | str | None = None,
    request_id: str | None = None,
    created_by: str = "local",
) -> Evaluation:
    """Inferencia local + persistencia; usada por el consumidor SQS."""

    from .ml import risk_model

    prediction = risk_model.predict_details(features)
    return store_evaluation(
        session,
        zone,
        features,
        prediction,
        source=source,
        observed_at=observed_at,
        request_id=request_id,
        created_by=created_by,
    )
