from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sigrif.api import main
from sigrif.config import settings
from sigrif.db import get_session
from sigrif.events import MessagingDisabled
from sigrif.ia.client import IAUnavailable
from sigrif.models import Alert

ZONE = SimpleNamespace(
    id=1,
    name="Valparaiso",
    display_name="Valparaiso",
    comuna="Valparaiso",
    provincia="Valparaíso",
    region="Valparaíso",
    zone_type="sector_municipal",
    name_source="SIG Municipalidad de Valparaíso",
    name_official=True,
    risk_level="Bajo",
    risk_score=0.12,
    vegetation=0.3,
    historical_fires=0,
    slope=15.0,
    fuel_native=0.0,
    fuel_plantation=0.0,
    fuel_shrub=0.0,
    fuel_grass=0.0,
    fuel_agriculture=0.0,
    fuel_urban=1.0,
    dominant_fuel="Urbano",
    last_source=None,
    last_alert_at=None,
    updated_at=datetime.now(UTC),
)

FEATURES = {
    "temperature": 35.0,
    "humidity": 20.0,
    "wind_speed": 60.0,
    "vegetation": 0.9,
    "historical_fires": 8,
    "slope": 30.0,
}

PREDICTION = {
    "risk_level": "Alto",
    "risk_score": 0.91,
    "probabilities": {"Bajo": 0.01, "Medio": 0.08, "Alto": 0.91},
    "model_version": "random-forest-0.2.0",
    "factors": [
        {
            "feature": "temperature",
            "label": "Temperatura",
            "value": 35.0,
            "unit": "°C",
            "impact": 0.3,
            "direction": "aumenta",
        }
    ],
    "scenario": {
        "description": "Escenario de reducción de vegetación",
        "risk_level": "Medio",
        "risk_score": 0.55,
        "delta": -0.36,
    },
}


OCR_RESULT = {
    "filename": "ficha.png",
    "content_type": "image/png",
    "size_bytes": 40,
    "text": "PTCL-23\nCHILE",
    "model_id": "amazon.nova-lite-v1:0",
    "latency_ms": 850.0,
    "usage": {"input_tokens": 1200, "output_tokens": 18},
    "truncated": False,
    "cached": False,
    "image_sha256": "a" * 64,
}

PNG = b"\x89PNG\r\n\x1a\n" + b"ficha" * 8


class FakeScalars:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        return iter(self.items)

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def scalars(self, statement):
        if "readings" in str(statement) or "field_reports" in str(statement):
            return FakeScalars([])
        return FakeScalars([ZONE])

    def scalar(self, statement):
        text = str(statement)
        if "ST_AsGeoJSON" in text:
            return '{"type": "MultiPolygon", "coordinates": []}'
        if "count" in text:
            return 1
        if "max" in text:
            return ZONE.updated_at
        return None

    def get(self, _, key):
        return ZONE if key == 1 else None

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = 1

    def refresh(self, _item):
        return None

    def commit(self):
        self.committed = True
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = 1
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime.now(UTC)


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


def test_version():
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["model_version"] == "random-forest-0.2.0"
    assert response.headers["X-Model-Version"] == "random-forest-0.2.0"


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
    assert "historical_fires" in published[0]


def test_simulate_without_messaging(monkeypatch):
    def disabled(_payload):
        raise MessagingDisabled("sin mensajería")

    monkeypatch.setattr(main, "publish_reading", disabled)
    main.app.dependency_overrides[get_session] = fake_session
    response = client.post("/api/v1/simulate")
    main.app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "no está habilitada" in response.json()["detail"]


def test_zones_are_public(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/zones")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200


def test_simulate_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    main.app.dependency_overrides[get_session] = fake_session
    response = client.post("/api/v1/simulate")
    main.app.dependency_overrides.clear()
    assert response.status_code == 401


def test_status():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/status")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["zones"] == 1
    assert response.json()["model_version"] == "random-forest-0.2.0"


def test_zone_history_empty():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/zones/1/history")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == []


def test_evaluate_zone_persists_reading(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(main, "predict_risk", lambda features, **_: PREDICTION)
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.post("/api/v1/zones/1/evaluate", json=FEATURES)
    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "Alto"
    assert body["prescription"]
    assert body["model_version"] == "random-forest-0.2.0"
    assert session.committed is True
    assert session.added[0].historical_fires == 8


def test_evaluate_zone_creates_alert(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(main, "predict_risk", lambda features, **_: PREDICTION)
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.post("/api/v1/zones/1/evaluate", json=FEATURES)
    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    alerts = [item for item in session.added if isinstance(item, Alert)]
    assert len(alerts) == 1
    assert alerts[0].zone_id == 1
    assert alerts[0].status == "nueva"


def test_evaluate_zone_does_not_create_alert_for_low_risk(monkeypatch):
    session = FakeSession()
    low = {**PREDICTION, "risk_level": "Bajo", "risk_score": 0.12}
    monkeypatch.setattr(main, "predict_risk", lambda features, **_: low)
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.post("/api/v1/zones/1/evaluate", json=FEATURES)
    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert not [item for item in session.added if isinstance(item, Alert)]


def test_evaluate_zone_forwards_request_id(monkeypatch):
    session = FakeSession()
    captured = {}

    def capture(features, **kwargs):
        captured.update(kwargs)
        return PREDICTION

    monkeypatch.setattr(main, "predict_risk", capture)
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.post(
        "/api/v1/zones/1/evaluate",
        json=FEATURES,
        headers={"X-Request-ID": "req-api-123"},
    )
    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-api-123"
    assert captured["request_id"] == "req-api-123"


def test_evaluate_zone_returns_503_when_ia_is_down(monkeypatch):
    def unavailable(_features, **_):
        raise IAUnavailable("sin conexión")

    monkeypatch.setattr(main, "predict_risk", unavailable)
    main.app.dependency_overrides[get_session] = fake_session
    response = client.post("/api/v1/zones/1/evaluate", json=FEATURES)
    main.app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


def test_evaluate_zone_validates_features(monkeypatch):
    monkeypatch.setattr(main, "predict_risk", lambda features, **_: PREDICTION)
    main.app.dependency_overrides[get_session] = fake_session
    invalid = {**FEATURES, "humidity": 140}
    response = client.post("/api/v1/zones/1/evaluate", json=invalid)
    main.app.dependency_overrides.clear()
    assert response.status_code == 422


def test_evaluate_zone_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    main.app.dependency_overrides[get_session] = fake_session
    response = client.post("/api/v1/zones/1/evaluate", json=FEATURES)
    main.app.dependency_overrides.clear()
    assert response.status_code == 401


def test_ocr_field_report_success(monkeypatch):
    captured = {}

    def fake_ocr(image_bytes, filename, content_type, **kwargs):
        captured.update(
            {
                "size": len(image_bytes),
                "filename": filename,
                "content_type": content_type,
                "request_id": kwargs.get("request_id"),
            }
        )
        return OCR_RESULT

    monkeypatch.setattr(main, "ocr_image", fake_ocr)
    response = client.post(
        "/api/v1/field-reports/ocr",
        files={"file": ("ficha.png", PNG, "image/png")},
        headers={"X-Request-ID": "req-ocr-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "PTCL-23\nCHILE"
    assert body["filename"] == "ficha.png"
    assert captured == {
        "size": len(PNG),
        "filename": "ficha.png",
        "content_type": "image/png",
        "request_id": "req-ocr-123",
    }


def test_ocr_field_report_returns_503(monkeypatch):
    def unavailable(*args, **kwargs):
        raise IAUnavailable("sin bedrock")

    monkeypatch.setattr(main, "ocr_image", unavailable)
    response = client.post(
        "/api/v1/field-reports/ocr",
        files={"file": ("ficha.png", PNG, "image/png")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


def test_create_field_report():
    session = FakeSession()
    main.app.dependency_overrides[get_session] = lambda: session
    response = client.post(
        "/api/v1/zones/1/field-reports",
        json={
            "extracted_text": "PTCL-23\nCHILE",
            "confirmed_text": "PTCL-23\nCHILE",
            "model_id": "amazon.nova-lite-v1:0",
            "source_filename": "ficha.png",
            "content_type": "image/png",
            "size_bytes": len(PNG),
        },
    )
    main.app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["zone_id"] == 1
    assert body["confirmed_text"] == "PTCL-23\nCHILE"
    assert body["status"] == "confirmed"
    assert session.committed is True


def test_list_field_reports_empty():
    main.app.dependency_overrides[get_session] = fake_session
    response = client.get("/api/v1/zones/1/field-reports")
    main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == []
