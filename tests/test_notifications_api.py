from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sigrif.api import main
from sigrif.config import settings
from sigrif.db import get_session
from sigrif.models import Evaluation, Notification, Zone

NOW = datetime.now(UTC)

ZONE = SimpleNamespace(id=1, name="Cerro Ñielol", comuna="Valparaíso")

NOTIFICATION = SimpleNamespace(
    id=10,
    zone_id=ZONE.id,
    alert_id=5,
    evaluation_id=7,
    event_type="cambio_nivel",
    level_from="Medio",
    level_to="Alto",
    title="El nivel de riesgo sube de Medio a Alto",
    detail="Cerro Ñielol (Valparaíso). Evaluación #7 con P(Alto)=0.82.",
    actor="operadora",
    created_at=NOW,
    read_at=None,
    read_by=None,
)

EVALUATION = SimpleNamespace(
    id=7,
    zone_id=ZONE.id,
    risk_level="Alto",
    risk_score=0.82,
    model_version="random-forest-0.2.0",
    source="manual",
    created_at=NOW,
    created_by="operadora",
    prescription=[{"title": "Reforzar patrullaje"}],
)


class FakeScalars:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class FakeSession:
    def __init__(self):
        self.notification = SimpleNamespace(**NOTIFICATION.__dict__)
        self.committed = False

    def scalars(self, statement):
        text = str(statement)
        if "FROM notifications" in text:
            return FakeScalars([self.notification])
        if "FROM zones" in text:
            return FakeScalars([ZONE])
        return FakeScalars([])

    def scalar(self, statement):
        text = str(statement)
        if "count" in text:
            return 1 if "read_at IS NULL" in text else 2
        return None

    def execute(self, statement):
        del statement
        return None

    def get(self, model, key):
        if model is Notification and key == self.notification.id:
            return self.notification
        if model is Zone and key == ZONE.id:
            return ZONE
        if model is Evaluation and key == EVALUATION.id:
            return EVALUATION
        return None

    def commit(self):
        self.committed = True

    def refresh(self, _item):
        return None


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(session: FakeSession) -> TestClient:
    main.app.dependency_overrides[get_session] = lambda: session
    return TestClient(main.app)


def test_list_notifications_includes_zone_and_link(client: TestClient) -> None:
    response = client.get("/api/v1/notifications")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["zone_name"] == "Cerro Ñielol"
    assert body[0]["comuna"] == "Valparaíso"
    assert body[0]["alert_id"] == 5
    assert body[0]["level_from"] == "Medio"
    assert body[0]["read_at"] is None


def test_notifications_summary(client: TestClient) -> None:
    response = client.get("/api/v1/notifications/summary")

    assert response.status_code == 200
    assert response.json() == {"total": 2, "unread": 1}


def test_mark_notification_read(client: TestClient, session: FakeSession) -> None:
    response = client.patch(f"/api/v1/notifications/{NOTIFICATION.id}/read")

    assert response.status_code == 200
    body = response.json()
    assert body["read_at"] is not None
    assert body["read_by"] == "local"
    assert session.committed is True


def test_mark_all_notifications_read(client: TestClient, session: FakeSession) -> None:
    response = client.patch("/api/v1/notifications/read-all")

    assert response.status_code == 200
    assert response.json() == {"total": 2, "unread": 1}
    assert session.committed is True


def test_notification_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/notifications/999/read")

    assert response.status_code == 404


def test_notifications_require_operator(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    response = client.get("/api/v1/notifications")

    assert response.status_code == 401


def test_evaluations_expose_history_fields(client: TestClient, session: FakeSession) -> None:
    def execute(_statement):
        return SimpleNamespace(all=lambda: [(EVALUATION, ZONE.name, ZONE.comuna)])

    session.execute = execute

    response = client.get("/api/v1/evaluations?risk_level=Alto")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["zone_name"] == "Cerro Ñielol"
    assert body[0]["comuna"] == "Valparaíso"
    assert body[0]["created_by"] == "operadora"
    assert body[0]["risk_score"] == 0.82


def test_evaluations_reject_invalid_level(client: TestClient) -> None:
    response = client.get("/api/v1/evaluations?risk_level=Extremo")

    assert response.status_code == 422
