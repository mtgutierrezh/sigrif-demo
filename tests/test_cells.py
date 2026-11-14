from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement

from sigrif.api import main
from sigrif.config import settings
from sigrif.db import get_session
from sigrif.models import RiskCell

CELL = SimpleNamespace(
    h3="88b2c40825fffff",
    geometry=WKTElement("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", srid=4326),
    zone_id=7,
    comuna="Valparaíso",
    provincia="Valparaíso",
    zone_name="SECTOR CENTRO",
    dominant_fuel="urban",
    fuel_native=0.0,
    fuel_plantation=0.0,
    fuel_shrub=0.0,
    fuel_grass=0.0,
    fuel_agriculture=0.0,
    fuel_urban=0.64,
    slope=12.5,
    historical_fires=3,
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
    def __init__(self):
        self.last_statement = ""

    def scalars(self, statement):
        self.last_statement = str(statement)
        return FakeScalars([CELL])


def fake_session():
    return FakeSession()


client = TestClient(main.app)


def test_risk_cell_has_regional_columns():
    columns = set(RiskCell.__table__.columns.keys())
    expected = {
        "h3",
        "zone_id",
        "comuna",
        "provincia",
        "zone_name",
        "slope",
        "historical_fires",
        "risk_level",
        "risk_score",
    }
    assert expected <= columns


def test_list_cells_returns_feature_collection():
    session = FakeSession()
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/api/v1/cells")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["h3"] == "88b2c40825fffff"
    assert body["features"][0]["geometry"]["type"] == "Polygon"
    assert body["features"][0]["properties"]["zone_name"] == "SECTOR CENTRO"
    assert body["features"][0]["properties"]["comuna"] == "Valparaíso"
    assert "LIMIT" in session.last_statement.upper()


def test_list_cells_respects_limit():
    session = FakeSession()
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/api/v1/cells?limit=25")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "LIMIT" in session.last_statement.upper()


def test_list_cells_rejects_excessive_limit():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get(f"/api/v1/cells?limit={settings.cells_max_limit + 1}")
    main.app.dependency_overrides.clear()
    assert response.status_code == 422


def test_cells_bbox_returns_feature_collection():
    session = FakeSession()
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.get(
        "/api/v1/cells/bbox?min_lon=-71.7&min_lat=-33.1&max_lon=-71.5&max_lat=-33.0"
    )
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["h3"] == "88b2c40825fffff"
    assert body["features"][0]["properties"]["slope"] == 12.5
    assert body["meta"]["count"] == 1
    assert body["meta"]["bbox"] == [-71.7, -33.1, -71.5, -33.0]
    assert "ST_Intersects" in session.last_statement
    assert "LIMIT" in session.last_statement.upper()


def test_cells_bbox_requires_all_bounds():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/cells/bbox?min_lon=-71.7&min_lat=-33.1")
    main.app.dependency_overrides.clear()
    assert response.status_code == 422


def test_cells_bbox_rejects_inverted_bounds():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get(
        "/api/v1/cells/bbox?min_lon=-71.5&min_lat=-33.0&max_lon=-71.7&max_lat=-33.1"
    )
    main.app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "bbox inválida" in response.json()["detail"]


def test_cells_bbox_rejects_excessive_limit():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get(
        "/api/v1/cells/bbox?min_lon=-71.7&min_lat=-33.1&max_lon=-71.5&max_lat=-33.0"
        f"&limit={settings.cells_bbox_max_limit + 1}"
    )
    main.app.dependency_overrides.clear()
    assert response.status_code == 422


def test_cells_bbox_filters_by_comuna():
    session = FakeSession()
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.get(
        "/api/v1/cells/bbox?min_lon=-71.7&min_lat=-33.1&max_lon=-71.5"
        "&max_lat=-33.0&comuna=Valpara%C3%ADso"
    )
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "comuna" in session.last_statement
