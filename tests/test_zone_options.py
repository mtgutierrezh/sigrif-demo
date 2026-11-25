from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sigrif.api import main
from sigrif.db import get_session


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
                "CREATE TABLE zones (id INTEGER PRIMARY KEY, name VARCHAR(80), "
                "comuna VARCHAR(80), risk_level VARCHAR(10), risk_score FLOAT, "
                "vegetation FLOAT, historical_fires INTEGER, slope FLOAT, "
                "dominant_fuel VARCHAR(40))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO zones VALUES "
                "(1, 'Cerro Ñielol', 'Valparaíso', 'Medio', 0.42, 0.6, 12, 18.5, 'Bosque nativo')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO zones VALUES "
                "(2, 'Cerro Alegre', 'Valparaíso', 'Bajo', 0.03, 0.1, 0, 4.2, 'Urbano')"
            )
        )
    return engine


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[get_session] = override
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


def test_zone_options_is_light_and_sorted(client: TestClient) -> None:
    response = client.get("/api/v1/zones/options")
    assert response.status_code == 200
    payload = response.json()
    assert [row["name"] for row in payload] == ["Cerro Alegre", "Cerro Ñielol"]
    assert set(payload[0]) == {
        "id",
        "name",
        "display_name",
        "comuna",
        "risk_level",
        "risk_score",
        "vegetation",
        "historical_fires",
        "slope",
        "dominant_fuel",
        "population",
    }
    assert "geometry" not in payload[0]
    assert "latest_reading" not in payload[0]
