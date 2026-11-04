from sigrif.ml import risk_model
from sigrif.model_spec import FEATURES, LABELS

HIGH_RISK = {
    "temperature": 40.0,
    "humidity": 10.0,
    "wind_speed": 80.0,
    "vegetation": 1.0,
    "historical_fires": 15,
    "slope": 40.0,
}

LOW_RISK = {
    "temperature": 10.0,
    "humidity": 85.0,
    "wind_speed": 3.0,
    "vegetation": 0.05,
    "historical_fires": 0,
    "slope": 1.0,
}


def test_high_risk_features_return_alto():
    label, score = risk_model.predict(HIGH_RISK)
    assert label == "Alto"
    assert 0.0 <= score <= 1.0


def test_low_risk_features_return_bajo():
    label, _ = risk_model.predict(LOW_RISK)
    assert label == "Bajo"


def test_details_include_explanations_and_scenario():
    result = risk_model.predict_details(HIGH_RISK)
    assert result["risk_level"] == "Alto"
    assert result["probabilities"]["Alto"] > 0.5
    assert len(result["factors"]) == 3
    assert {factor["feature"] for factor in result["factors"]} <= set(FEATURES)
    assert result["scenario"] is not None
    assert result["model_version"]


def test_model_info_has_features_and_metrics():
    info = risk_model.info()
    assert info["features"] == list(FEATURES)
    assert info["labels"] == list(LABELS)
    assert "accuracy" in info["metrics"]
