"""Entrena, evalúa y registra el modelo de riesgo de SIGRIF.

Uso local:
    uv run python scripts/train_model.py --cross-validate

El artefacto queda en ``artifacts/risk_model.joblib`` y los metadatos en
``ml/model_metadata.json`` y ``ml/metrics.json``. No se usa MLflow: el registro
es un artefacto versionado en S3 más sus metadatos JSON.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sigrif.model_spec import DEFAULT_DATASET_SIZE, DEFAULT_SEED
from sigrif.training import save_artifact, train_classifier, write_dataset_csv

ROOT = Path(__file__).resolve().parents[1]


def _parse_s3(uri: str) -> tuple[str, str]:
    bucket, key = uri.removeprefix("s3://").split("/", 1)
    return bucket, key.rstrip("/")


def _upload(files: list[Path], destination: str) -> None:
    import boto3

    bucket, prefix = _parse_s3(destination)
    client = boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
    )
    for path in files:
        key = f"{prefix}/{path.name}" if prefix else path.name
        client.upload_file(str(path), bucket, key)
        print(f"Subido: s3://{bucket}/{key}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena el Random Forest de SIGRIF")
    parser.add_argument("--dataset-size", type=int, default=DEFAULT_DATASET_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--cross-validate", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=ROOT / "data" / "training" / "sigrif_risk_synthetic.csv",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=ROOT / "ml" / "model_metadata.json",
    )
    parser.add_argument(
        "--metrics-path",
        type=Path,
        default=ROOT / "ml" / "metrics.json",
    )
    parser.add_argument("--upload-s3", type=str, default=None)
    args = parser.parse_args()

    result = train_classifier(
        size=args.dataset_size,
        seed=args.seed,
        test_size=args.test_size,
        cross_validate=args.cross_validate,
    )
    dataset_path = write_dataset_csv(result.rows, args.dataset_path)
    artifact_path = save_artifact(
        result,
        artifact_path=args.output_dir / "risk_model.joblib",
        metadata_path=args.metadata_path,
        metrics_path=args.metrics_path,
    )

    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))
    print(f"Dataset: {dataset_path}")
    print(f"Artefacto: {artifact_path}")
    print(f"Metadatos: {args.metadata_path}")
    print(f"Métricas: {args.metrics_path}")

    if args.upload_s3:
        _upload(
            [artifact_path, dataset_path, args.metadata_path, args.metrics_path],
            args.upload_s3,
        )


if __name__ == "__main__":
    main()
