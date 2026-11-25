from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sigrif.evaluation import store_evaluation
from sigrif.models import Alert, AlertEvent, Evaluation, Notification, Reading
from sigrif.notifications import record_alert_opened, record_level_change


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    for table in (
        Reading.__table__,
        Evaluation.__table__,
        Alert.__table__,
        AlertEvent.__table__,
        Notification.__table__,
    ):
        table.create(engine)
    with Session(engine) as db_session:
        yield db_session


def make_zone(level: str = "Medio") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Cerro Ñielol",
        comuna="Valparaíso",
        risk_level=level,
        risk_score=0.4,
        last_source=None,
        last_alert_at=None,
    )


def make_evaluation(level: str = "Alto", score: float = 0.82) -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        zone_id=1,
        risk_level=level,
        risk_score=score,
        created_by="operadora",
    )


def test_level_change_creates_one_notification(session: Session) -> None:
    zone = make_zone("Medio")
    evaluation = make_evaluation("Alto")

    first = record_level_change(session, zone, evaluation, "Medio", actor="operadora")
    second = record_level_change(session, zone, evaluation, "Medio", actor="operadora")
    session.commit()

    assert first is not None
    assert second is None
    stored = session.scalars(select(Notification)).all()
    assert len(stored) == 1
    assert stored[0].event_type == "cambio_nivel"
    assert stored[0].level_from == "Medio"
    assert stored[0].level_to == "Alto"
    assert "Medio" in stored[0].title and "Alto" in stored[0].title
    assert stored[0].actor == "operadora"


def test_level_change_ignores_same_or_unknown_level(session: Session) -> None:
    zone = make_zone("Alto")

    assert record_level_change(session, zone, make_evaluation("Alto"), "Alto") is None
    assert record_level_change(session, zone, make_evaluation("Alto"), None) is None
    assert record_level_change(session, zone, make_evaluation("Alto"), "Desconocido") is None
    assert session.scalars(select(Notification)).all() == []


def test_alert_opened_is_not_duplicated(session: Session) -> None:
    zone = make_zone("Medio")
    evaluation = make_evaluation("Alto")
    alert = SimpleNamespace(id=5)

    first = record_alert_opened(session, zone, evaluation, alert, actor="operadora")
    second = record_alert_opened(session, zone, evaluation, alert, actor="operadora")
    session.commit()

    assert first is not None
    assert second is None
    stored = session.scalars(select(Notification)).all()
    assert len(stored) == 1
    assert stored[0].event_type == "alerta_alto"
    assert stored[0].alert_id == 5
    assert stored[0].level_to == "Alto"


def test_store_evaluation_notifies_level_change_and_alert(session: Session) -> None:
    zone = make_zone("Medio")
    evaluation = store_evaluation(
        session,
        zone,
        {
            "temperature": 35.0,
            "humidity": 20.0,
            "wind_speed": 60.0,
            "vegetation": 0.9,
            "historical_fires": 8,
            "slope": 30.0,
        },
        {
            "risk_level": "Alto",
            "risk_score": 0.91,
            "probabilities": {"Bajo": 0.01, "Medio": 0.08, "Alto": 0.91},
            "model_version": "random-forest-0.2.0",
            "factors": [],
            "scenario": None,
        },
        source="manual",
        created_by="operadora",
    )

    assert evaluation.id is not None
    assert zone.risk_level == "Alto"
    notifications = session.scalars(select(Notification)).all()
    assert {item.event_type for item in notifications} == {"cambio_nivel", "alerta_alto"}


def test_store_evaluation_does_not_repeat_notifications(session: Session) -> None:
    zone = make_zone("Bajo")
    prediction = {
        "risk_level": "Alto",
        "risk_score": 0.91,
        "probabilities": {"Bajo": 0.01, "Medio": 0.08, "Alto": 0.91},
        "model_version": "random-forest-0.2.0",
        "factors": [],
        "scenario": None,
    }
    features = {
        "temperature": 35.0,
        "humidity": 20.0,
        "wind_speed": 60.0,
        "vegetation": 0.9,
        "historical_fires": 8,
        "slope": 30.0,
    }

    store_evaluation(session, zone, features, prediction, created_by="operadora")
    store_evaluation(session, zone, features, prediction, created_by="operadora")

    notifications = session.scalars(select(Notification)).all()
    assert len(notifications) == 2
    assert {item.event_type for item in notifications} == {"cambio_nivel", "alerta_alto"}
    alerts = session.scalars(select(Alert)).all()
    assert len(alerts) == 1


def test_notification_payload_includes_zone() -> None:
    from sigrif.notifications import notification_payload

    notification = SimpleNamespace(
        id=9,
        zone_id=1,
        alert_id=None,
        evaluation_id=10,
        event_type="cambio_nivel",
        level_from="Medio",
        level_to="Alto",
        title="Cambio",
        detail="Detalle",
        actor="operadora",
        created_at=datetime.now(UTC),
        read_at=None,
        read_by=None,
    )
    zone = SimpleNamespace(id=1, name="Cerro Ñielol", comuna="Valparaíso")

    payload = notification_payload(notification, zone)

    assert payload["zone_name"] == "Cerro Ñielol"
    assert payload["comuna"] == "Valparaíso"
