from sigrif.ml import LABELS, risk_model


def test_high_risk_features_return_alto():
    label, score = risk_model.predict([40.0, 10.0, 80.0, 1.0, 40.0])
    assert label == "Alto"
    assert 0.0 <= score <= 1.0


def test_low_risk_features_return_bajo():
    label, _ = risk_model.predict([10.0, 85.0, 3.0, 0.05, 1.0])
    assert label == "Bajo"


def test_labels_are_stable():
    assert LABELS == ("Bajo", "Medio", "Alto")
