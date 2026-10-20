from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement

from sigrif.api import main
from sigrif.db import get_session

CELL = SimpleNamespace(
    h3="88b2c40825fffff",
    geometry=WKTElement("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", srid=4326),
    dominant_fuel="urban",
    fuel_native=0.0,
    fuel_plantation=0.0,
    fuel_shrub=0.0,
    fuel_grass=0.0,
    fuel_agriculture=0.0,
    fuel_urban=0.64,
    wui_distance_m=0.0,
    risk_level="Bajo",
    risk_score=0.3,
    updated_at=datetime.now(UTC),
)


class FakeScalars:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class FakeSession:
    def scalars(self, _):
        return FakeScalars([CELL])


def fake_session():
    return FakeSession()


client = TestClient(main.app)


def test_list_cells_returns_feature_collection():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/cells")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["h3"] == "88b2c40825fffff"
    assert body["features"][0]["geometry"]["type"] == "Polygon"
