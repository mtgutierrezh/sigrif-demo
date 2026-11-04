#!/bin/sh
set -eu

API_HOST="${API_HOST:-api:8000}"
LISTEN_PORT="${LISTEN_PORT:-80}"
SERVER_NAME="${SERVER_NAME:-_}"

mkdir -p /etc/nginx/upstream
if [ ! -f /etc/nginx/upstream/active.conf ]; then
  echo "server ${API_HOST} max_fails=3 fail_timeout=15s;" > /etc/nginx/upstream/active.conf
fi

if [ "$SERVER_NAME" != "_" ]; then
  if [ -f "/etc/letsencrypt/live/${SERVER_NAME}/fullchain.pem" ]; then
    TEMPLATE="/etc/nginx/nginx.prod.https.conf"
  else
    TEMPLATE="/etc/nginx/nginx.prod.http.conf"
  fi
else
  TEMPLATE="/etc/nginx/nginx.conf.template"
fi

envsubst '${API_HOST} ${LISTEN_PORT} ${SERVER_NAME}' < "$TEMPLATE" > /etc/nginx/nginx.conf
nginx -t
exec nginx -g 'daemon off;'
