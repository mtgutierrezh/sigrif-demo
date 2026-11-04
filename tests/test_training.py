import json

import joblib

from sigrif.model_spec import FEATURES, MODEL_VERSION
from sigrif.training import save_artifact, train_classifier


def test_training_reports_metrics_and_feature_importance() -> None:
    result = train_classifier(size=180, seed=7, test_size=0.25)

    assert result.metrics["dataset_size"] == 180
    assert result.metrics["train_size"] == 135
    assert result.metrics["test_size"] == 45
    assert 0.0 <= result.metrics["accuracy"] <= 1.0
    assert set(result.metrics["f1_per_class"]) == {"Bajo", "Medio", "Alto"}
    assert len(result.feature_importance) == len(FEATURES)
    assert result.dataset_hash == train_classifier(size=180, seed=7, test_size=0.25).dataset_hash


def test_save_artifact_writes_model_metadata_and_metrics(tmp_path) -> None:
    result = train_classifier(size=120, seed=11)
    artifact = tmp_path / "risk_model.joblib"
    metadata = tmp_path / "metadata.json"
    metrics = tmp_path / "metrics.json"

    saved = save_artifact(
        result,
        artifact_path=artifact,
        metadata_path=metadata,
        metrics_path=metrics,
    )

    assert saved == artifact
    payload = joblib.load(artifact)
    assert payload["version"] == MODEL_VERSION
    assert payload["features"] == list(FEATURES)
    assert "model" in payload

    metadata_payload = json.loads(metadata.read_text())
    metrics_payload = json.loads(metrics.read_text())
    assert metadata_payload["dataset_hash"] == result.dataset_hash
    assert metrics_payload["accuracy"] == result.metrics["accuracy"]
    assert "model" not in metadata_payload
