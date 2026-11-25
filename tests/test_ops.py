from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sigrif import ops
from sigrif.api import main
from sigrif.db import get_session
from sigrif.ops import predominant_variables

NOW = datetime.now(UTC)

ZONE = SimpleNamespace(
    id=3,
    name="Cerro Ñielol",
    display_name="Cerro Ñielol",
    comuna="Valparaíso",
    risk_level="Alto",
    risk_score=0.91,
    last_source="dmc",
    last_alert_at=NOW,
    updated_at=NOW,
)


class FakeSession:
    def __init__(self):
        self.last_run = SimpleNamespace(
            id=4,
            provider="dmc",
            status="ok",
            started_at=NOW - timedelta(minutes=20),
            zones_ok=563,
            zones_total=563,
        )

    def scalar(self, statement):
        text = str(statement)
        if "PostGIS_Version" in text:
            return "3.4 USE_GEOS=1 USE_PROJ=1"
        return None

    def scalars(self, statement):
        del statement
        return SimpleNamespace(first=lambda: self.last_run, all=lambda: [self.last_run])


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    main.app.dependency_overrides.clear()


def test_predominant_variables_are_sorted() -> None:
    items = predominant_variables()

    assert len(items) == 6
    assert items == sorted(items, key=lambda item: item["importance"], reverse=True)
    assert {item["source"] for item in items} <= {"modelo", "pesos_documentados"}


def test_executive_endpoint_returns_cards_and_critical_zones(monkeypatch) -> None:
    summary = {
        "generated_at": NOW,
        "zones": 563,
        "risk_counts": {"Bajo": 400, "Medio": 140, "Alto": 23},
        "critical_zones": [ZONE],
        "active_alerts": 15,
        "high_risk_zones": 23,
        "alerts_by_status": {"nueva": 10, "en_revision": 5, "cerrada": 8},
        "variation": {
            "evaluations_24h": 40,
            "evaluations_previous_24h": 32,
            "evaluations_delta": 8,
            "alerts_24h": 4,
            "alerts_previous_24h": 6,
            "alerts_delta": -2,
        },
        "predominant_variables": [
            {
                "feature": "temperature",
                "label": "Temperatura",
                "importance": 0.3705,
                "source": "modelo",
            }
        ],
        "sources": [{"source": "dmc", "readings": 500, "last_at": NOW}],
        "model_version": "random-forest-0.2.0",
    }
    monkeypatch.setattr(main, "build_executive_summary", lambda session: summary)
    main.app.dependency_overrides[get_session] = lambda: FakeSession()

    response = TestClient(main.app).get("/api/v1/ops/executive")

    assert response.status_code == 200
    body = response.json()
    assert body["risk_counts"]["Alto"] == 23
    assert body["critical_zones"][0]["name"] == "Cerro Ñielol"
    assert body["variation"]["evaluations_delta"] == 8
    assert body["predominant_variables"][0]["feature"] == "temperature"
    assert body["sources"][0]["source"] == "dmc"


def test_services_endpoint_returns_six_checks(monkeypatch) -> None:
    payload = {
        "checked_at": NOW,
        "status": "degraded",
        "services": [
            {"key": "api", "label": "API", "status": "ok", "detail": "FastAPI en línea"},
            {"key": "ia", "label": "IA", "status": "ok", "detail": "Modelo disponible"},
            {"key": "postgis", "label": "PostGIS", "status": "ok", "detail": "PostGIS 3.4"},
            {"key": "sqs", "label": "SQS", "status": "degraded", "detail": "Sin cola"},
            {
                "key": "ingesta",
                "label": "Ingesta",
                "status": "ok",
                "detail": "dmc: 563/563 zonas",
            },
            {
                "key": "frescura",
                "label": "Frescura",
                "status": "degraded",
                "detail": "60 min desde la última lectura",
            },
        ],
        "queue_depth": None,
        "last_ingest": NOW - timedelta(minutes=60),
        "freshness_minutes": 60.0,
        "stale": True,
    }
    monkeypatch.setattr(
        main,
        "build_service_status",
        lambda session, p95_ms=None: payload,
    )
    main.app.dependency_overrides[get_session] = lambda: FakeSession()

    response = TestClient(main.app).get("/api/v1/ops/services")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert [item["key"] for item in body["services"]] == [
        "api",
        "ia",
        "postgis",
        "sqs",
        "ingesta",
        "frescura",
    ]


def test_build_service_status_marks_degraded_freshness(monkeypatch) -> None:
    monkeypatch.setattr(ops, "check_ia_service", lambda: ("ok", "IA disponible"))
    monkeypatch.setattr(ops, "queue_depth", lambda: 3)
    monkeypatch.setattr(
        ops,
        "data_timestamps",
        lambda session: (NOW - timedelta(minutes=60), "dmc"),
    )

    payload = ops.build_service_status(FakeSession(), p95_ms=42.0)

    assert payload["status"] == "degraded"
    assert payload["queue_depth"] == 3
    assert payload["stale"] is True
    checks = {item["key"]: item for item in payload["services"]}
    assert checks["frescura"]["status"] == "degraded"
    assert checks["postgis"]["status"] == "ok"
    assert checks["ingesta"]["status"] == "ok"
    assert checks["api"]["status"] == "ok"
