from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sigrif.api import main
from sigrif.db import get_session
from sigrif.models import PreventiveAction


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE zones (id INTEGER PRIMARY KEY, name VARCHAR(80), comuna VARCHAR(80))"
            )
        )
        connection.execute(
            text("CREATE TABLE alerts (id INTEGER PRIMARY KEY, zone_id INTEGER NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO zones (id, name, comuna) VALUES (1, 'Cerro Ñielol', 'Valparaíso')")
        )
        connection.execute(
            text("INSERT INTO zones (id, name, comuna) VALUES (2, 'Cerro Alegre', 'Valparaíso')")
        )
        connection.execute(text("INSERT INTO alerts (id, zone_id) VALUES (5, 1)"))
        connection.execute(text("INSERT INTO alerts (id, zone_id) VALUES (6, 2)"))
    PreventiveAction.__table__.create(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def client(engine):
    def override():
        with Session(engine) as db_session:
            yield db_session

    main.app.dependency_overrides[get_session] = override
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def add_action(
    session: Session,
    *,
    zone_id: int = 1,
    kind: str = "accion",
    status: str = "pendiente",
    title: str = "Limpieza de vegetación seca",
    due_date: date | None = None,
) -> PreventiveAction:
    action = PreventiveAction(
        zone_id=zone_id,
        kind=kind,
        category="vegetacion_seca",
        title=title,
        detail="Detalle operativo",
        status=status,
        priority="media",
        created_by="operadora",
        due_date=due_date,
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def test_create_action_with_alert_and_zone(client: TestClient) -> None:
    response = client.post(
        "/api/v1/actions",
        json={
            "zone_id": 1,
            "alert_id": 5,
            "kind": "accion",
            "category": "vegetacion_seca",
            "title": "Despejar franja de seguridad",
            "detail": "Coordinar con la brigada comunal.",
            "priority": "alta",
            "assigned_to": "Turno norte",
            "due_date": "2020-01-01",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["zone_name"] == "Cerro Ñielol"
    assert body["comuna"] == "Valparaíso"
    assert body["alert_id"] == 5
    assert body["created_by"] == "local"
    assert body["status"] == "pendiente"
    assert body["overdue"] is True


def test_create_action_validates_zone_and_alert(client: TestClient) -> None:
    payload = {
        "zone_id": 99,
        "kind": "accion",
        "category": "otro",
        "title": "Revisar acceso",
    }
    assert client.post("/api/v1/actions", json=payload).status_code == 404

    payload["zone_id"] = 1
    payload["alert_id"] = 6
    response = client.post("/api/v1/actions", json=payload)
    assert response.status_code == 422
    assert "no pertenece a la zona" in response.json()["detail"]

    payload["alert_id"] = 999
    response = client.post("/api/v1/actions", json=payload)
    assert response.status_code == 422
    assert "no existe" in response.json()["detail"]


def test_create_action_rejects_invalid_enums(client: TestClient) -> None:
    base = {"zone_id": 1, "category": "otro", "title": "Revisar acceso"}
    assert client.post("/api/v1/actions", json={**base, "kind": "otro"}).status_code == 422
    assert client.post("/api/v1/actions", json={**base, "priority": "urgente"}).status_code == 422
    assert client.post("/api/v1/actions", json={**base, "category": ""}).status_code == 422
    assert client.post("/api/v1/actions", json={**base, "title": "   "}).status_code == 422


def test_list_actions_filters_and_overdue(client: TestClient, session: Session) -> None:
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    add_action(session, zone_id=1, due_date=yesterday, title="Pendiente vencida")
    add_action(
        session,
        zone_id=2,
        kind="incidente",
        status="en_ejecucion",
        title="Incidente abierto",
    )
    add_action(session, zone_id=1, status="completada", title="Acción cerrada")

    pending = client.get("/api/v1/actions?status=pendiente")
    assert pending.status_code == 200
    assert [item["title"] for item in pending.json()] == ["Pendiente vencida"]
    assert pending.json()[0]["overdue"] is True

    incidents = client.get("/api/v1/actions?kind=incidente")
    assert incidents.status_code == 200
    assert [item["title"] for item in incidents.json()] == ["Incidente abierto"]

    zone_one = client.get("/api/v1/actions?zone_id=1")
    assert zone_one.status_code == 200
    assert len(zone_one.json()) == 2
    assert {item["zone_name"] for item in zone_one.json()} == {"Cerro Ñielol"}

    assert client.get("/api/v1/actions?status=invalido").status_code == 422
    assert client.get("/api/v1/actions?kind=invalido").status_code == 422


def test_action_transitions_manage_closed_at(client: TestClient, session: Session) -> None:
    action = add_action(session, title="Revisar microbasural")

    started = client.patch(
        f"/api/v1/actions/{action.id}",
        json={"status": "en_ejecucion", "assigned_to": "Brigada 2"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "en_ejecucion"
    assert started.json()["closed_at"] is None

    completed = client.patch(
        f"/api/v1/actions/{action.id}",
        json={
            "status": "completada",
            "detail": "Retiro terminado.",
            "due_date": "2026-12-01",
            "priority": "alta",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completada"
    assert completed.json()["closed_at"] is not None
    assert completed.json()["detail"] == "Retiro terminado."
    assert completed.json()["priority"] == "alta"
    assert completed.json()["due_date"] == "2026-12-01"

    reopened = client.patch(f"/api/v1/actions/{action.id}", json={"status": "pendiente"})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "pendiente"
    assert reopened.json()["closed_at"] is None


def test_patch_action_validates_and_handles_missing(client: TestClient, session: Session) -> None:
    action = add_action(session)

    assert client.patch("/api/v1/actions/9999", json={"status": "completada"}).status_code == 404
    response = client.patch(f"/api/v1/actions/{action.id}", json={"priority": "urgente"})
    assert response.status_code == 422


def test_actions_summary_counts_status_overdue_and_incidents(
    client: TestClient, session: Session
) -> None:
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    add_action(session, zone_id=1, due_date=yesterday)
    add_action(session, zone_id=2, kind="incidente", status="pendiente")
    add_action(session, zone_id=1, kind="incidente", status="completada", due_date=yesterday)
    add_action(session, zone_id=2, status="completada")

    response = client.get("/api/v1/actions/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total": 4,
        "pendiente": 2,
        "en_ejecucion": 0,
        "completada": 2,
        "cancelada": 0,
        "overdue": 1,
        "open_incidents": 1,
    }
