import csv
import io
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sigrif.api import main
from sigrif.config import settings
from sigrif.db import get_session
from sigrif.models import Evaluation, Reading, Zone
from sigrif.reports import zone_csv_bytes, zone_pdf_bytes

NOW = datetime.now(UTC)

ZONE = SimpleNamespace(id=7, name="Cerro Ñielol", comuna="Valparaíso")
READING = SimpleNamespace(
    observed_at=NOW,
    temperature=35.0,
    humidity=20.0,
    wind_speed=60.0,
)
EVALUATION = SimpleNamespace(
    id=21,
    zone_id=ZONE.id,
    reading_id=5,
    risk_level="Alto",
    risk_score=0.93,
    model_version="random-forest-0.2.0",
    source="manual",
    created_at=NOW,
    features={
        "temperature": 35.0,
        "humidity": 20.0,
        "wind_speed": 60.0,
        "vegetation": 0.9,
        "historical_fires": 8,
        "slope": 30.0,
    },
    factors=[
        {
            "feature": "temperature",
            "label": "Temperatura",
            "value": 35.0,
            "unit": "°C",
            "impact": 0.3,
            "direction": "aumenta",
        }
    ],
    scenario={
        "description": "Escenario de reducción de vegetación",
        "risk_level": "Medio",
        "risk_score": 0.55,
        "delta": -0.36,
    },
    prescription=[
        {
            "code": "patrullaje_inmediato",
            "title": "Reforzar patrullaje en el sector",
            "description": "Asignar una ronda terrestre prioritaria.",
            "priority": "inmediata",
            "horizon": "24 h",
            "rationale": "El modelo estimó riesgo Alto.",
        }
    ],
)


class FakeScalars:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class ReportSession:
    def __init__(self, *, evaluation=EVALUATION, zones=(ZONE,)):
        self.evaluation = evaluation
        self.zones = list(zones)
        self.committed = False

    def get(self, model, key):
        if model is Zone:
            return next((zone for zone in self.zones if zone.id == key), None)
        if model is Reading:
            return READING if key == EVALUATION.reading_id else None
        if model is Evaluation:
            return self.evaluation if key == EVALUATION.id else None
        return None

    def scalars(self, statement):
        text = str(statement)
        if "FROM zones" in text:
            return FakeScalars(self.zones)
        if "FROM evaluations" in text:
            return FakeScalars([self.evaluation] if self.evaluation is not None else [])
        return FakeScalars([])


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    main.app.dependency_overrides.clear()


def make_client(session: ReportSession) -> TestClient:
    main.app.dependency_overrides[get_session] = lambda: session
    return TestClient(main.app)


def test_zone_csv_contains_requested_columns() -> None:
    payload = zone_csv_bytes(ZONE, EVALUATION, READING, EVALUATION.prescription)
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))

    assert rows[0][:7] == [
        "Zona",
        "Comuna",
        "Nivel de riesgo",
        "Score",
        "Modelo",
        "Fuente",
        "Fecha",
    ]
    assert rows[0][7:] == ["Variables", "Factores", "Escenario", "Acciones"]
    assert rows[1][0] == "Cerro Ñielol"
    assert rows[1][1] == "Valparaíso"
    assert rows[1][2] == "Alto"
    assert rows[1][3] == "0.93"
    assert "Temperatura: 35.00 °C" in rows[1][7]
    assert "Temperatura: aumenta" in rows[1][8]
    assert "reducción de vegetación" in rows[1][9]
    assert "Reforzar patrullaje" in rows[1][10]


def test_zone_pdf_has_pdf_signature_and_content() -> None:
    payload = zone_pdf_bytes(ZONE, EVALUATION, READING, EVALUATION.prescription)

    assert payload.startswith(b"%PDF-")
    assert b"SIGRIF" in payload
    assert len(payload) > 2_000


def test_zone_report_csv_endpoint() -> None:
    client = make_client(ReportSession())

    response = client.get(f"/api/v1/zones/{ZONE.id}/report.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"] == 'attachment; filename="sigrif-cerro-nielol.csv"'
    )
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "Variables" in response.content.decode("utf-8-sig")


def test_zone_report_pdf_endpoint() -> None:
    client = make_client(ReportSession())

    response = client.get(f"/api/v1/zones/{ZONE.id}/report.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="sigrif-cerro-nielol.pdf"'
    )
    assert response.content.startswith(b"%PDF-")


def test_zone_report_returns_404_without_evaluation() -> None:
    client = make_client(ReportSession(evaluation=None))

    response = client.get(f"/api/v1/zones/{ZONE.id}/report.csv")

    assert response.status_code == 404
    assert "evaluaciones" in response.json()["detail"]


def test_zone_report_returns_404_for_unknown_zone() -> None:
    client = make_client(ReportSession())

    response = client.get("/api/v1/zones/999/report.pdf")

    assert response.status_code == 404


def test_zones_report_csv_endpoint() -> None:
    client = make_client(ReportSession())

    response = client.get("/api/v1/reports/zones.csv")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="sigrif-zonas.csv"'
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == [
        "Zona",
        "Comuna",
        "Nivel de riesgo",
        "Score",
        "Modelo",
        "Fuente",
        "Fecha",
        "Acciones",
    ]
    assert rows[1][0] == "Cerro Ñielol"


def test_zones_report_returns_404_without_evaluations() -> None:
    client = make_client(ReportSession(evaluation=None))

    response = client.get("/api/v1/reports/zones.csv")

    assert response.status_code == 404
    assert "evaluaciones" in response.json()["detail"]


def test_reports_require_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    client = make_client(ReportSession())

    response = client.get(f"/api/v1/zones/{ZONE.id}/report.csv")

    assert response.status_code == 401
