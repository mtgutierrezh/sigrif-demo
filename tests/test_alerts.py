from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sigrif.alerts import add_event, ensure_alert, update_alert
from sigrif.models import Alert, AlertEvent

ZONE = SimpleNamespace(id=7, name="Cerro Ñielol", comuna="Valparaíso")


def make_evaluation(
    evaluation_id: int,
    *,
    score: float = 0.91,
    level: str = "Alto",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=evaluation_id,
        zone_id=ZONE.id,
        risk_level=level,
        risk_score=score,
        created_by="operadora",
    )


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Alert.__table__.create(engine)
    AlertEvent.__table__.create(engine)
    with Session(engine) as db_session:
        yield db_session


def events_for(session: Session, alert_id: int) -> list[AlertEvent]:
    return list(
        session.scalars(
            select(AlertEvent).where(AlertEvent.alert_id == alert_id).order_by(AlertEvent.id)
        ).all()
    )


def test_ensure_alert_creates_one_open_alert(session: Session) -> None:
    evaluation = make_evaluation(11)

    alert = ensure_alert(session, ZONE, evaluation)
    session.commit()

    assert alert.id is not None
    assert alert.status == "nueva"
    assert alert.evaluation_id == evaluation.id
    events = events_for(session, alert.id)
    assert [event.event_type for event in events] == ["creada"]
    assert "0.91" in (events[0].detail or "")
    assert events[0].actor == "operadora"


def test_ensure_alert_reclassifies_without_duplicating(session: Session) -> None:
    first = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()
    second = ensure_alert(session, ZONE, make_evaluation(12, score=0.97))
    session.commit()

    assert second.id == first.id
    assert second.evaluation_id == 12
    assert session.scalar(select(Alert).where(Alert.zone_id == ZONE.id)) is not None
    assert len(list(session.scalars(select(Alert)).all())) == 1
    events = events_for(session, second.id)
    assert [event.event_type for event in events] == ["creada", "reclasificada"]
    assert "0.97" in (events[1].detail or "")


def test_ensure_alert_creates_a_new_alert_after_closing(session: Session) -> None:
    first = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()
    update_alert(session, first, status="cerrada", actor="operadora")
    session.commit()

    second = ensure_alert(session, ZONE, make_evaluation(12))
    session.commit()

    assert second.id != first.id
    assert first.closed_at is not None
    assert len(list(session.scalars(select(Alert)).all())) == 2


def test_update_alert_records_each_change(session: Session) -> None:
    alert = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()

    update_alert(
        session,
        alert,
        status="en_revision",
        assigned_to="turno norte",
        comment="Revisar acceso por camino La Pólvora.",
        actor="operadora",
    )
    session.commit()

    assert alert.status == "en_revision"
    assert alert.assigned_to == "turno norte"
    assert alert.comment == "Revisar acceso por camino La Pólvora."
    assert alert.closed_at is None
    assert alert.updated_at is not None
    events = events_for(session, alert.id)
    assert [event.event_type for event in events] == [
        "creada",
        "estado",
        "asignacion",
        "comentario",
    ]
    assert events[1].detail == "nueva -> en_revision"
    assert events[1].actor == "operadora"


def test_update_alert_closes_and_reopens(session: Session) -> None:
    alert = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()

    update_alert(session, alert, status="cerrada", actor="operadora")
    session.commit()
    assert alert.closed_at is not None

    update_alert(session, alert, status="nueva", actor="operadora")
    session.commit()
    assert alert.closed_at is None


def test_update_alert_rejects_invalid_status(session: Session) -> None:
    alert = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()
    before = len(events_for(session, alert.id))

    with pytest.raises(ValueError, match="Estado de alerta inválido"):
        update_alert(session, alert, status="desconocida", actor="operadora")

    assert len(events_for(session, alert.id)) == before


def test_update_alert_ignores_same_values(session: Session) -> None:
    alert = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()
    before = len(events_for(session, alert.id))

    update_alert(
        session,
        alert,
        status="nueva",
        assigned_to=None,
        comment=None,
        actor="operadora",
    )
    session.commit()

    assert len(events_for(session, alert.id)) == before


def test_add_event_manual(session: Session) -> None:
    alert = ensure_alert(session, ZONE, make_evaluation(11))
    session.commit()

    event = add_event(
        session,
        alert,
        "llamada",
        detail="Se contactó a la brigada comunal.",
        actor="operadora",
    )
    session.commit()

    assert event.id is not None
    assert event.alert_id == alert.id
    assert event.event_type == "llamada"
    assert event.created_at is not None
    assert [item.event_type for item in events_for(session, alert.id)] == ["creada", "llamada"]
