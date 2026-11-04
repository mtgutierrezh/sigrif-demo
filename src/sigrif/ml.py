"""Carga del modelo de riesgo y explicación local de sus predicciones."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .model_spec import (
    DEFAULT_SEED,
    FEATURE_LABELS,
    FEATURE_UNITS,
    FEATURES,
    LABEL_TO_INDEX,
    LABELS,
    LOW_RISK_BASELINES,
    feature_vector,
)
from .training import artifact_payload, train_classifier

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_PATH = Path(os.getenv("SIGRIF_MODEL_PATH", "artifacts/risk_model.joblib"))
MODEL_S3_URI = os.getenv("SIGRIF_MODEL_S3_URI")
FALLBACK_SAMPLES = int(os.getenv("SIGRIF_FALLBACK_SAMPLES", "600"))


def _download_from_s3(uri: str, destination: Path) -> None:
    """Descarga el artefacto desde S3 cuando el despliegue lo configura."""

    import boto3

    from .config import settings

    bucket, key = uri.removeprefix("s3://").split("/", 1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
    )
    client.download_file(bucket, key, str(destination))


class RiskModel:
    """Envoltorio del Random Forest con metadatos y explicaciones locales."""

    def __init__(
        self,
        artifact_path: str | Path | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.artifact_path = Path(artifact_path or DEFAULT_ARTIFACT_PATH)
        self._model: Any = None
        self._metadata: dict[str, Any] = {}
        self._load_or_train(allow_fallback)

    def _load_or_train(self, allow_fallback: bool) -> None:
        if MODEL_S3_URI and not self.artifact_path.exists():
            try:
                _download_from_s3(MODEL_S3_URI, self.artifact_path)
                logger.info("Modelo descargado desde %s", MODEL_S3_URI)
            except Exception:
                logger.warning("No se pudo descargar el modelo desde S3", exc_info=True)

        if self.artifact_path.exists():
            try:
                payload = joblib.load(self.artifact_path)
                if isinstance(payload, dict) and "model" in payload:
                    artifact_features = tuple(payload.get("features", ()))
                    if artifact_features and artifact_features != FEATURES:
                        raise ValueError("El artefacto no coincide con las variables esperadas")
                    self._model = payload["model"]
                    self._metadata = {
                        key: value for key, value in payload.items() if key != "model"
                    }
                    self._metadata["source"] = "artifact"
                elif hasattr(payload, "predict_proba"):
                    self._model = payload
                    self._metadata = {
                        "version": "legacy",
                        "features": list(FEATURES),
                        "labels": list(LABELS),
                        "source": "legacy-artifact",
                    }
                else:
                    raise ValueError("Formato de artefacto no reconocido")
                logger.info("Modelo cargado desde %s", self.artifact_path)
                return
            except Exception:
                logger.exception("No se pudo cargar el artefacto %s", self.artifact_path)

        if not allow_fallback:
            raise RuntimeError("No hay artefacto de modelo disponible")

        logger.warning("Entrenando modelo de respaldo en memoria (solo desarrollo)")
        result = train_classifier(size=FALLBACK_SAMPLES, seed=DEFAULT_SEED, cross_validate=False)
        payload = artifact_payload(result)
        self._model = result.classifier
        self._metadata = {key: value for key, value in payload.items() if key != "model"}
        self._metadata["source"] = "fallback-training"

    @property
    def model_version(self) -> str:
        return str(self._metadata.get("version", "unknown"))

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    @property
    def feature_importance(self) -> list[dict[str, Any]]:
        return list(self._metadata.get("feature_importance", []))

    def info(self) -> dict[str, Any]:
        """Resumen apto para el endpoint de metadatos del servicio de IA."""

        return {
            "version": self.model_version,
            "features": list(FEATURES),
            "labels": list(LABELS),
            "trained_at": self._metadata.get("trained_at"),
            "dataset_hash": self._metadata.get("dataset_hash"),
            "metrics": self._metadata.get("metrics", {}),
            "feature_importance": self.feature_importance,
            "source": self._metadata.get("source"),
        }

    def _probabilities(self, values: Sequence[float]) -> dict[str, float]:
        probabilities = self._model.predict_proba(np.asarray([values], dtype=float))[0]
        classes = [int(label) for label in self._model.classes_]
        result = {label: 0.0 for label in LABELS}
        for class_index, probability in zip(classes, probabilities, strict=True):
            result[LABELS[class_index]] = float(probability)
        return result

    @staticmethod
    def _label(probabilities: Mapping[str, float]) -> str:
        return max(LABELS, key=lambda label: probabilities[label])

    def _factors(
        self,
        values: Sequence[float],
        base_probabilities: Mapping[str, float],
    ) -> list[dict[str, Any]]:
        """Sensibilidad local: cuánto baja el riesgo si cada variable mejora."""

        variants = []
        for feature in FEATURES:
            variant = list(values)
            variant[FEATURES.index(feature)] = LOW_RISK_BASELINES[feature]
            variants.append(variant)

        probabilities = self._model.predict_proba(np.asarray(variants, dtype=float))
        classes = [int(label) for label in self._model.classes_]
        alto_index = classes.index(LABEL_TO_INDEX["Alto"])
        base_alto = float(base_probabilities["Alto"])

        factors: list[dict[str, Any]] = []
        for index, feature in enumerate(FEATURES):
            impact = base_alto - float(probabilities[index][alto_index])
            factors.append(
                {
                    "feature": feature,
                    "label": FEATURE_LABELS[feature],
                    "value": round(float(values[index]), 4),
                    "unit": FEATURE_UNITS[feature],
                    "impact": round(impact, 4),
                    "direction": (
                        "aumenta" if impact > 0.01 else "reduce" if impact < -0.01 else "neutro"
                    ),
                }
            )

        return sorted(factors, key=lambda factor: factor["impact"], reverse=True)[:3]

    def _scenario(
        self,
        values: Sequence[float],
        base_probabilities: Mapping[str, float],
    ) -> dict[str, Any] | None:
        """Contrafactual de gestión de combustible, una palanca realmente accionable."""

        vegetation_index = FEATURES.index("vegetation")
        current = float(values[vegetation_index])
        if current < 0.2:
            return None

        modified = list(values)
        modified[vegetation_index] = round(max(0.0, current - 0.2), 4)
        probabilities = self._probabilities(modified)
        return {
            "description": (
                "Si se reduce la vegetación combustible en 0.20, el modelo estima "
                "el siguiente escenario de riesgo."
            ),
            "risk_level": self._label(probabilities),
            "risk_score": round(probabilities["Alto"], 4),
            "delta": round(probabilities["Alto"] - base_probabilities["Alto"], 4),
        }

    def predict_details(self, values: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
        vector = feature_vector(values)
        probabilities = self._probabilities(vector)
        risk_level = self._label(probabilities)
        return {
            "risk_level": risk_level,
            "risk_score": round(probabilities["Alto"], 4),
            "probabilities": {label: round(value, 4) for label, value in probabilities.items()},
            "model_version": self.model_version,
            "factors": self._factors(vector, probabilities),
            "scenario": self._scenario(vector, probabilities),
        }

    def predict(self, values: Mapping[str, Any] | Sequence[Any]) -> tuple[str, float]:
        """Interfaz compatible con el consumidor anterior del servicio de IA."""

        result = self.predict_details(values)
        return str(result["risk_level"]), float(result["risk_score"])


risk_model = RiskModel()
