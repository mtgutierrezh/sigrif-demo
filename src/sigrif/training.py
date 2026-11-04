"""Entrenamiento reproducible y evaluación del modelo de riesgo de SIGRIF."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from .model_spec import (
    DEFAULT_DATASET_SIZE,
    DEFAULT_SEED,
    FEATURE_LABELS,
    FEATURES,
    LABELS,
    MODEL_VERSION,
    dataset_matrix,
    synthetic_rows,
)

MODEL_PARAMS: dict[str, Any] = {
    "n_estimators": 160,
    "max_depth": 10,
    "min_samples_leaf": 3,
    "class_weight": "balanced",
    "random_state": DEFAULT_SEED,
    "n_jobs": -1,
}


@dataclass(slots=True)
class TrainingResult:
    classifier: RandomForestClassifier
    rows: list[dict[str, Any]]
    metrics: dict[str, Any]
    dataset_hash: str
    trained_at: str
    feature_importance: list[dict[str, Any]]
    params: dict[str, Any]


def _csv_text(rows: list[dict[str, Any]]) -> str:
    fieldnames = ["sample_id", *FEATURES, "rule_score", "risk_level"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def dataset_hash(rows: list[dict[str, Any]]) -> str:
    """Hash estable del contenido del dataset, útil para trazabilidad."""

    return hashlib.sha256(_csv_text(rows).encode("utf-8")).hexdigest()


def write_dataset_csv(rows: list[dict[str, Any]], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_csv_text(rows), encoding="utf-8")
    return destination


def _evaluate(
    classifier: RandomForestClassifier,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> dict[str, Any]:
    predictions = classifier.predict(x_test)
    probabilities = classifier.predict_proba(x_test)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, predictions, labels=list(range(len(LABELS))), zero_division=0
    )

    metrics: dict[str, Any] = {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "macro_f1": round(float(f1_score(y_test, predictions, average="macro")), 4),
        "weighted_f1": round(float(f1_score(y_test, predictions, average="weighted")), 4),
        "precision_per_class": {
            LABELS[index]: round(float(precision[index]), 4) for index in range(len(LABELS))
        },
        "recall_per_class": {
            LABELS[index]: round(float(recall[index]), 4) for index in range(len(LABELS))
        },
        "f1_per_class": {LABELS[index]: round(float(f1[index]), 4) for index in range(len(LABELS))},
        "support_per_class": {LABELS[index]: int(support[index]) for index in range(len(LABELS))},
        "confusion_matrix": confusion_matrix(
            y_test, predictions, labels=list(range(len(LABELS)))
        ).tolist(),
        "classification_report": classification_report(
            y_test,
            predictions,
            labels=list(range(len(LABELS))),
            target_names=list(LABELS),
            output_dict=True,
            zero_division=0,
        ),
    }

    try:
        metrics["roc_auc_ovr"] = round(
            float(
                roc_auc_score(
                    y_test,
                    probabilities,
                    multi_class="ovr",
                    labels=list(range(len(LABELS))),
                )
            ),
            4,
        )
    except ValueError:
        metrics["roc_auc_ovr"] = None

    return metrics


def train_classifier(
    size: int = DEFAULT_DATASET_SIZE,
    seed: int = DEFAULT_SEED,
    test_size: float = 0.2,
    cross_validate: bool = False,
    n_splits: int = 5,
) -> TrainingResult:
    """Genera datos, entrena el Random Forest y calcula métricas de evaluación."""

    rows = synthetic_rows(size=size, seed=seed)
    features, labels = dataset_matrix(rows)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=test_size,
        random_state=seed,
        stratify=labels,
    )

    params = {**MODEL_PARAMS, "random_state": seed}
    classifier = RandomForestClassifier(**params)
    classifier.fit(x_train, y_train)

    metrics = _evaluate(classifier, x_test, y_test)
    metrics["train_size"] = int(len(x_train))
    metrics["test_size"] = int(len(x_test))
    metrics["dataset_size"] = int(size)
    metrics["seed"] = seed

    if cross_validate:
        folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        scores = cross_val_score(
            classifier,
            features,
            labels,
            cv=folds,
            scoring="f1_macro",
            n_jobs=-1,
        )
        metrics["cross_validation"] = {
            "folds": n_splits,
            "metric": "f1_macro",
            "scores": [round(float(score), 4) for score in scores],
            "mean": round(float(np.mean(scores)), 4),
            "std": round(float(np.std(scores)), 4),
        }

    importance = [
        {
            "feature": feature,
            "label": FEATURE_LABELS[feature],
            "importance": round(float(value), 4),
        }
        for feature, value in sorted(
            zip(FEATURES, classifier.feature_importances_, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return TrainingResult(
        classifier=classifier,
        rows=rows,
        metrics=metrics,
        dataset_hash=dataset_hash(rows),
        trained_at=datetime.now(UTC).isoformat(),
        feature_importance=importance,
        params=params,
    )


def artifact_payload(result: TrainingResult) -> dict[str, Any]:
    return {
        "model": result.classifier,
        "features": list(FEATURES),
        "labels": list(LABELS),
        "version": MODEL_VERSION,
        "trained_at": result.trained_at,
        "dataset_hash": result.dataset_hash,
        "metrics": result.metrics,
        "feature_importance": result.feature_importance,
        "params": result.params,
    }


def save_artifact(
    result: TrainingResult,
    artifact_path: str | Path,
    metadata_path: str | Path | None = None,
    metrics_path: str | Path | None = None,
) -> Path:
    """Guarda el modelo y sus metadatos; no usa MLflow a propósito."""

    destination = Path(artifact_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = artifact_payload(result)
    joblib.dump(payload, destination)

    metadata = {key: value for key, value in payload.items() if key != "model"}
    if metadata_path is not None:
        metadata_destination = Path(metadata_path)
        metadata_destination.parent.mkdir(parents=True, exist_ok=True)
        metadata_destination.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if metrics_path is not None:
        metrics_destination = Path(metrics_path)
        metrics_destination.parent.mkdir(parents=True, exist_ok=True)
        metrics_destination.write_text(
            json.dumps(metadata["metrics"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return destination
