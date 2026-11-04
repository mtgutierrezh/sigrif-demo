#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source /opt/sigrif/.env
set +a

if [ -z "${DOMAIN:-}" ]; then
  echo "Falta DOMAIN en /opt/sigrif/.env" >&2
  exit 1
fi

if [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  echo "Falta LETSENCRYPT_EMAIL en /opt/sigrif/.env" >&2
  exit 1
fi

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file /opt/sigrif/.env)

"${COMPOSE[@]}" up -d nginx
"${COMPOSE[@]}" --profile tools run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring

"${COMPOSE[@]}" restart nginx
sleep 3
curl -fsS "https://$DOMAIN/health"
echo
echo "TLS listo para $DOMAIN"
