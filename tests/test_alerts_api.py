from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sigrif.api import main
from sigrif.auth import get_current_user
from sigrif.config import settings
from sigrif.db import get_session
from sigrif.models import Alert, AlertEvent, Evaluation, Zone

NOW = datetime.now(UTC)

ZONE = SimpleNamespace(
    id=7,
    name="Cerro Ñielol",
    comuna="Valparaíso",
    risk_level="Alto",
    risk_score=0.93,
)

EVALUATION = SimpleNamespace(
    id=21,
    zone_id=ZONE.id,
    risk_level="Alto",
    risk_score=0.93,
    model_version="random-forest-0.2.0",
    source="manual",
    created_at=NOW,
    prescription=[{"title": "Reforzar patrullaje"}],
)

ALERT = SimpleNamespace(
    id=31,
    zone_id=ZONE.id,
    evaluation_id=EVALUATION.id,
    status="nueva",
    assigned_to=None,
    comment=None,
    created_at=NOW,
    updated_at=NOW,
    closed_at=None,
)

EVENT = SimpleNamespace(
    id=41,
    alert_id=ALERT.id,
    event_type="creada",
    detail="Evaluación #21: nivel Alto con score 0.93.",
    actor="operadora",
    created_at=NOW,
)


class FakeScalars:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class FakeResult:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items


class AlertSession:
    def __init__(self):
        self.alerts = [SimpleNamespace(**ALERT.__dict__)]
        self.events = [SimpleNamespace(**EVENT.__dict__)]
        self.committed = False

    def scalars(self, statement):
        text = str(statement)
        if "alert_events" in text:
            return FakeScalars(self.events)
        if "FROM alerts" in text:
            return FakeScalars(self.alerts)
        return FakeScalars([])

    def scalar(self, statement):
        if "FROM alerts" in str(statement):
            open_alerts = [alert for alert in self.alerts if alert.status != "cerrada"]
            return open_alerts[-1] if open_alerts else None
        return None

    def execute(self, statement):
        del statement
        counts = {}
        for alert in self.alerts:
            counts[alert.status] = counts.get(alert.status, 0) + 1
        return FakeResult(list(counts.items()))

    def get(self, model, key):
        if model is Zone:
            return ZONE if key == ZONE.id else None
        if model is Evaluation:
            return EVALUATION if key == EVALUATION.id else None
        if model is Alert:
            return next((alert for alert in self.alerts if alert.id == key), None)
        return None

    def add(self, item):
        if isinstance(item, AlertEvent):
            if item.alert_id is None and item.alert is not None:
                item.alert_id = item.alert.id
            if getattr(item, "id", None) is None:
                item.id = 100 + len(self.events)
            self.events.append(item)
        elif isinstance(item, Alert):
            if getattr(item, "id", None) is None:
                item.id = 100 + len(self.alerts)
            self.alerts.append(item)

    def flush(self):
        for item in [*self.alerts, *self.events]:
            if getattr(item, "id", None) is None:
                item.id = 100

    def commit(self):
        self.committed = True
        for event in self.events:
            if getattr(event, "created_at", None) is None:
                event.created_at = NOW

    def refresh(self, _item):
        return None

    def rollback(self):
        return None


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    main.app.dependency_overrides.clear()


def make_client(session: AlertSession) -> TestClient:
    main.app.dependency_overrides[get_session] = lambda: session
    return TestClient(main.app)


def test_list_alerts(client: TestClient) -> None:
    response = client.get("/api/v1/alerts")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["zone_name"] == "Cerro Ñielol"
    assert body[0]["comuna"] == "Valparaíso"
    assert body[0]["status"] == "nueva"
    assert body[0]["evaluation"]["model_version"] == "random-forest-0.2.0"


def test_list_alerts_rejects_invalid_status(client: TestClient) -> None:
    response = client.get("/api/v1/alerts?status=inventada")

    assert response.status_code == 422
    assert "inválido" in response.json()["detail"]


def test_alert_detail_includes_events(client: TestClient) -> None:
    response = client.get(f"/api/v1/alerts/{ALERT.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == ALERT.id
    assert body["events"][0]["event_type"] == "creada"


def test_alert_detail_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/alerts/999")

    assert response.status_code == 404


def test_patch_alert_records_changes(client: TestClient, session: AlertSession) -> None:
    response = client.patch(
        f"/api/v1/alerts/{ALERT.id}",
        json={
            "status": "en_revision",
            "assigned_to": "turno norte",
            "comment": "Revisar el acceso superior.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "en_revision"
    assert body["assigned_to"] == "turno norte"
    assert body["comment"] == "Revisar el acceso superior."
    assert [event["event_type"] for event in body["events"]][-3:] == [
        "estado",
        "asignacion",
        "comentario",
    ]
    assert session.committed is True


def test_patch_alert_closes_with_timestamp(client: TestClient) -> None:
    response = client.patch(f"/api/v1/alerts/{ALERT.id}", json={"status": "cerrada"})

    assert response.status_code == 200
    body = response.json()
    assert body["closed_at"] is not None
    assert body["events"][-1]["event_type"] == "estado"


def test_patch_alert_rejects_invalid_status(client: TestClient) -> None:
    response = client.patch(f"/api/v1/alerts/{ALERT.id}", json={"status": "otra"})

    assert response.status_code == 422


def test_create_manual_event(client: TestClient, session: AlertSession) -> None:
    response = client.post(
        f"/api/v1/alerts/{ALERT.id}/events",
        json={"event_type": "llamada", "detail": "Se avisó a la brigada comunal."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["event_type"] == "llamada"
    assert body["actor"] == "local"
    assert session.committed is True


def test_alert_summary_counts(client: TestClient) -> None:
    response = client.get("/api/v1/alerts/summary")

    assert response.status_code == 200
    assert response.json() == {"total": 1, "nueva": 1, "en_revision": 0, "cerrada": 0}


def test_alerts_require_token(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    response = client.get("/api/v1/alerts")

    assert response.status_code == 401


def test_alerts_require_operator_group(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    main.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "visitante",
        "cognito:groups": [],
    }

    response = client.get("/api/v1/alerts")

    assert response.status_code == 403


@pytest.fixture
def session() -> AlertSession:
    return AlertSession()


@pytest.fixture
def client(session: AlertSession) -> TestClient:
    return make_client(session)


def test_closed_alert_does_not_block_new_ones() -> None:
    closed = SimpleNamespace(
        **{
            **ALERT.__dict__,
            "status": "cerrada",
            "closed_at": NOW - timedelta(hours=1),
        }
    )
    session = AlertSession()
    session.alerts = [closed]

    assert session.scalar("SELECT * FROM alerts") is None
