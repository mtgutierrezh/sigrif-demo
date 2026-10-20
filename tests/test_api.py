from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sigrif.api import main
from sigrif.db import get_session

ZONE = SimpleNamespace(
    id=1,
    name="Valparaiso",
    comuna="Valparaiso",
    risk_level="Bajo",
    risk_score=0.12,
    updated_at=datetime.now(UTC),
)


class FakeScalars:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        return iter(self.items)

    def first(self):
        return self.items[0] if self.items else None


class FakeSession:
    def scalars(self, _):
        return FakeScalars([ZONE])

    def get(self, _, key):
        return ZONE if key == 1 else None


def fake_session():
    return FakeSession()


client = TestClient(main.app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "sigrif_api_requests_total" in response.text


def test_list_zones():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/zones")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Valparaiso"


def test_get_zone_not_found():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/zones/99")
    main.app.dependency_overrides.clear()
    assert response.status_code == 404


def test_simulate_publishes(monkeypatch):
    published = []
    monkeypatch.setattr(main, "publish_reading", lambda payload: published.append(payload))
    main.app.dependency_overrides[get_session] = fake_session
    response = client.post("/api/v1/simulate")
    main.app.dependency_overrides.clear()
    assert response.status_code == 202
    assert published[0]["zone_id"] == 1
