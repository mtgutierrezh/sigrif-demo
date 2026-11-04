from types import SimpleNamespace

from sigrif.ia.main import apply_reading, predict
from sigrif.schemas import RiskFeaturesIn

PAYLOAD = {
    "zone_id": 1,
    "temperature": 35.0,
    "humidity": 20.0,
    "wind_speed": 60.0,
    "vegetation": 0.9,
    "historical_fires": 8,
    "slope": 30.0,
}


class FakeSession:
    def __init__(self, zone):
        self.zone = zone
        self.added = []
        self.committed = False

    def get(self, _, key):
        if self.zone is not None and key == self.zone.id:
            return self.zone
        return None

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True


def test_apply_reading_updates_zone():
    zone = SimpleNamespace(id=1, risk_level="Bajo", risk_score=0.0)
    session = FakeSession(zone)
    assert apply_reading(session, PAYLOAD) is True
    assert zone.risk_level in ("Bajo", "Medio", "Alto")
    assert session.committed is True
    assert len(session.added) == 1
    assert session.added[0].historical_fires == 8


def test_apply_reading_missing_zone():
    session = FakeSession(None)
    assert apply_reading(session, PAYLOAD) is False


def test_predict_endpoint_returns_prediction():
    features = {key: value for key, value in PAYLOAD.items() if key != "zone_id"}
    result = predict(RiskFeaturesIn(**features))
    assert result.risk_level in ("Bajo", "Medio", "Alto")
    assert 0.0 <= result.risk_score <= 1.0
    assert result.model_version
    assert len(result.factors) == 3
