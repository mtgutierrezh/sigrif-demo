#!/bin/bash
set -euo pipefail

: "${1:?Uso: publish_model.sh <bucket> [region]}"
BUCKET=$1
REGION=${2:-us-east-2}

cd "$(dirname "$0")/.."

for path in artifacts/risk_model.joblib ml/model_metadata.json ml/metrics.json; do
  if [ ! -f "$path" ]; then
    echo "Falta $path; ejecuta make train" >&2
    exit 1
  fi
done

aws s3 cp artifacts/risk_model.joblib \
  "s3://$BUCKET/models/risk_model.joblib" --region "$REGION"
aws s3 cp ml/model_metadata.json \
  "s3://$BUCKET/models/model_metadata.json" --region "$REGION"
aws s3 cp ml/metrics.json \
  "s3://$BUCKET/models/metrics.json" --region "$REGION"

echo "Modelo random-forest-0.2.0 publicado en s3://$BUCKET/models/"
