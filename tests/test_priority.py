import math
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sigrif.api import main
from sigrif.db import get_session
from sigrif.priority import (
    PRIORITY_WEIGHTS,
    build_priority_ranking,
    density_per_hectare,
    official_population_by_name,
    priority_level,
)


def make_zone(
    zone_id: int,
    name: str,
    *,
    score: float = 0.5,
    vegetation: float = 0.5,
    fires: int = 2,
    slope: float = 30.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=zone_id,
        name=name,
        comuna="Valparaíso",
        risk_level="Medio",
        risk_score=score,
        vegetation=vegetation,
        historical_fires=fires,
        slope=slope,
    )


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, statement):
        del statement
        return FakeResult(self.rows)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    main.app.dependency_overrides.clear()


def test_official_population_only_includes_positive_census_zones() -> None:
    population = official_population_by_name()

    assert len(population) == 51
    assert all(value > 0 for value in population.values())
    assert population["SECTOR CENTRO"] == 1438


def test_density_requires_population_and_valid_area() -> None:
    assert density_per_hectare(1438, 34.4) == pytest.approx(41.802, rel=1e-4)
    assert density_per_hectare(None, 34.4) is None
    assert density_per_hectare(1438, 0) is None
    assert density_per_hectare(1438, None) is None


def test_priority_uses_log_density_and_p95() -> None:
    zones = [
        make_zone(1, "Uno"),
        make_zone(2, "Dos"),
        make_zone(3, "Tres"),
    ]
    habitat = {1: 10.0, 2: 10.0, 3: 10.0}
    population = {"Uno": 100.0, "Dos": 1000.0}

    payload = build_priority_ranking(zones, habitat, population, limit=3)

    assert payload["population_coverage"] == {"known": 2, "total": 3}
    assert math.log1p(10.0) < payload["density_p95_log"] < math.log1p(100.0)
    by_name = {item["zone_name"]: item for item in payload["items"]}
    assert by_name["Dos"]["population_density"] == pytest.approx(100.0)
    assert by_name["Dos"]["components"][-1]["weight"] == 0.10
    assert by_name["Dos"]["components"][-1]["normalized"] == pytest.approx(1.0)
    assert by_name["Uno"]["components"][-1]["normalized"] < 1.0


def test_missing_population_renormalizes_weights() -> None:
    zones = [make_zone(1, "Sin población")]
    payload = build_priority_ranking(zones, {1: 12.0}, {}, limit=1)

    item = payload["items"][0]
    components = {component["key"]: component for component in item["components"]}

    assert item["population"] is None
    assert item["population_available"] is False
    assert item["density_available"] is False
    assert components["population_density"]["weight"] == 0
    assert components["population_density"]["normalized"] is None
    assert sum(component["weight"] for component in item["components"]) == pytest.approx(1.0)
    assert components["alto_probability"]["weight"] == pytest.approx(
        PRIORITY_WEIGHTS["alto_probability"] / (1 - PRIORITY_WEIGHTS["population_density"]),
        rel=1e-3,
    )
    assert 0 <= item["score"] <= 100


def test_zero_population_is_treated_as_missing() -> None:
    zones = [make_zone(1, "Sin población")]
    payload = build_priority_ranking(zones, {1: 12.0}, {"Sin población": 0.0}, limit=1)

    assert payload["population_coverage"] == {"known": 0, "total": 1}
    assert payload["items"][0]["population_available"] is False


def test_known_population_with_invalid_area_renormalizes_density() -> None:
    zones = [make_zone(1, "Área inválida")]
    payload = build_priority_ranking(zones, {1: 0.0}, {"Área inválida": 500.0}, limit=1)

    item = payload["items"][0]
    components = {component["key"]: component for component in item["components"]}

    assert item["population"] == 500.0
    assert item["population_available"] is True
    assert item["density_available"] is False
    assert components["population_density"]["weight"] == 0
    assert sum(component["weight"] for component in item["components"]) == pytest.approx(1.0)


def test_ranking_is_sorted_and_scores_capped() -> None:
    zones = [
        make_zone(1, "Bajo", score=0.1, vegetation=0.1, fires=0, slope=5),
        make_zone(2, "Alto", score=0.9, vegetation=0.9, fires=20, slope=60),
    ]
    payload = build_priority_ranking(zones, {1: 10.0, 2: 10.0}, {}, limit=2)

    assert [item["zone_id"] for item in payload["items"]] == [2, 1]
    assert [item["position"] for item in payload["items"]] == [1, 2]
    assert all(0 <= item["score"] <= 100 for item in payload["items"])
    assert payload["items"][0]["priority_level"] == priority_level(payload["items"][0]["score"])


def test_priority_endpoint_returns_components_and_coverage(monkeypatch) -> None:
    row = SimpleNamespace(
        zone_id=7,
        zone_name="Cerro Ñielol",
        comuna="Valparaíso",
        risk_level="Medio",
        risk_score=0.82,
        vegetation=0.5,
        historical_fires=4,
        slope=30.0,
        area_ha=28.5,
    )
    session = FakeSession([row])
    main.app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr(
        main,
        "official_population_by_name",
        lambda: {"Cerro Ñielol": 1200.0},
    )

    response = TestClient(main.app).get("/api/v1/ops/priority?limit=20")

    assert response.status_code == 200
    body = response.json()
    assert body["population_coverage"] == {"known": 1, "total": 1}
    assert body["items"][0]["zone_name"] == "Cerro Ñielol"
    assert body["items"][0]["population"] == 1200.0
    assert body["items"][0]["area_ha"] == 28.5
    assert len(body["items"][0]["components"]) == 5
    assert "no reemplaza el nivel de riesgo" in body["methodology_note"]
    assert body["methodology_note"].find("viviendas") > 0


def test_priority_level_thresholds() -> None:
    assert priority_level(45.0) == "Alta"
    assert priority_level(30.0) == "Media"
    assert priority_level(29.9) == "Baja"
