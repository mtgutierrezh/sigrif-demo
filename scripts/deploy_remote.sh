#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source /opt/sigrif/.env
# shellcheck disable=SC1091
source ./images.env
set +a

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file /opt/sigrif/.env)
ACTIVE_FILE=/opt/sigrif/nginx/upstream/active

if [ -f /opt/sigrif/ghcr_token ] && [ -n "${GHCR_USERNAME:-}" ]; then
  docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin < /opt/sigrif/ghcr_token
fi

mkdir -p /opt/sigrif/artifacts
aws s3 cp "s3://$S3_BUCKET/models/risk_model.joblib" \
  /opt/sigrif/artifacts/risk_model.joblib
aws s3 cp "s3://$S3_BUCKET/models/model_metadata.json" \
  /opt/sigrif/artifacts/model_metadata.json || true
aws s3 cp "s3://$S3_BUCKET/models/metrics.json" \
  /opt/sigrif/artifacts/metrics.json || true

if [ "${SKIP_PULL:-0}" != "1" ]; then
  "${COMPOSE[@]}" pull
fi
"${COMPOSE[@]}" up -d db ia

if [ ! -f "$ACTIVE_FILE" ]; then
  echo blue > "$ACTIVE_FILE"
  "${COMPOSE[@]}" up -d api-blue
  for _ in $(seq 1 30); do
    if "${COMPOSE[@]}" exec -T api-blue python -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"; then
      "${COMPOSE[@]}" up -d nginx
      "${COMPOSE[@]}" --profile tools run --rm seed
      echo "Primer despliegue: color activo blue"
      exit 0
    fi
    sleep 2
  done
  echo "La API blue no respondió al health check" >&2
  exit 1
fi

ACTIVE=$(cat "$ACTIVE_FILE")
if ! "${COMPOSE[@]}" ps --services --filter status=running | grep -qx "api-$ACTIVE"; then
  "${COMPOSE[@]}" up -d "api-$ACTIVE"
fi

"${COMPOSE[@]}" up -d nginx
"${COMPOSE[@]}" --profile tools run --rm seed
bash scripts/bluegreen_deploy.sh
