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
UPSTREAM_FILE=/opt/sigrif/nginx/upstream/active.conf

ACTIVE=$(cat "$ACTIVE_FILE")
if [ "$ACTIVE" = "blue" ]; then
  TARGET=green
else
  TARGET=blue
fi
OLD=$ACTIVE

restore() {
  echo "server api-$OLD:8000 max_fails=3 fail_timeout=15s;" > "$UPSTREAM_FILE"
  "${COMPOSE[@]}" exec -T nginx nginx -t >/dev/null 2>&1 || true
  "${COMPOSE[@]}" exec -T nginx nginx -s reload >/dev/null 2>&1 || true
}

cleanup_on_error() {
  restore
  "${COMPOSE[@]}" stop "api-$TARGET" >/dev/null 2>&1 || true
}

trap 'cleanup_on_error' ERR

"${COMPOSE[@]}" up -d --no-deps "api-$TARGET"

READY=0
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T "api-$TARGET" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

if [ "$READY" -ne 1 ]; then
  echo "El color $TARGET no respondió al health check" >&2
  "${COMPOSE[@]}" stop "api-$TARGET"
  exit 1
fi

echo "server api-$TARGET:8000 max_fails=3 fail_timeout=15s;" > "$UPSTREAM_FILE.new"
mv "$UPSTREAM_FILE.new" "$UPSTREAM_FILE"

"${COMPOSE[@]}" exec -T nginx nginx -t
"${COMPOSE[@]}" exec -T nginx nginx -s reload

sleep 2

if [ -n "${DOMAIN}" ] && [ -f "/opt/sigrif/certbot/conf/live/$DOMAIN/fullchain.pem" ]; then
  HEADERS=$(curl -fsS -D - -o /dev/null --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/health")
else
  HEADERS=$(curl -fsS -D - -o /dev/null "http://127.0.0.1/health")
fi

if ! echo "$HEADERS" | grep -qi "x-app-color: $TARGET"; then
  echo "El tráfico no llegó al color $TARGET; se restaura $OLD" >&2
  restore
  "${COMPOSE[@]}" stop "api-$TARGET"
  exit 1
fi

trap - ERR
echo "$TARGET" > "$ACTIVE_FILE"
echo "Blue-green correcto: $OLD -> $TARGET"

sleep 20
"${COMPOSE[@]}" stop "api-$OLD"
