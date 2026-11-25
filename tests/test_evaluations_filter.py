from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sigrif.api import main
from sigrif.db import get_session
from sigrif.models import Evaluation

NOW = datetime.now(UTC)


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
                "CREATE TABLE zones (id INTEGER PRIMARY KEY, name VARCHAR(80), comuna VARCHAR(80))"
            )
        )
        connection.execute(
            text("INSERT INTO zones (id, name, comuna) VALUES (1, 'Cerro Ñielol', 'Valparaíso')")
        )
    Evaluation.__table__.create(engine)
    with Session(engine) as session:
        for index, created_at in enumerate(
            (NOW - timedelta(hours=2), NOW - timedelta(hours=48)), start=1
        ):
            session.add(
                Evaluation(
                    id=index,
                    zone_id=1,
                    risk_level="Alto" if index == 1 else "Medio",
                    risk_score=0.8 if index == 1 else 0.4,
                    model_version="random-forest-0.2.0",
                    features={},
                    probabilities={"Alto": 0.8, "Medio": 0.2},
                    factors=[],
                    prescription=[],
                    source="manual",
                    created_by="operadora",
                    created_at=created_at,
                )
            )
        session.commit()
    return engine


@pytest.fixture
def client(engine):
    def override():
        with Session(engine) as db_session:
            yield db_session

    main.app.dependency_overrides[get_session] = override
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_evaluations_filter_since_hours(client: TestClient) -> None:
    recent = client.get("/api/v1/evaluations?since_hours=24")
    assert recent.status_code == 200
    assert [item["id"] for item in recent.json()] == [1]

    weekly = client.get("/api/v1/evaluations?since_hours=72")
    assert weekly.status_code == 200
    assert [item["id"] for item in weekly.json()] == [2, 1]

    everything = client.get("/api/v1/evaluations")
    assert everything.status_code == 200
    assert [item["id"] for item in everything.json()] == [2, 1]


def test_evaluations_reject_out_of_range_since_hours(client: TestClient) -> None:
    assert client.get("/api/v1/evaluations?since_hours=0").status_code == 422
    assert client.get("/api/v1/evaluations?since_hours=721").status_code == 422
