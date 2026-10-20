#!/usr/bin/env bash
set -euo pipefail

: "${COGNITO_USER_POOL_ID:?Define COGNITO_USER_POOL_ID}"
: "${COGNITO_TEST_PASSWORD:?Define COGNITO_TEST_PASSWORD}"

create_user() {
  local email="$1"
  local group="$2"
  local name="$3"

  aws cognito-idp admin-create-user \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$email" \
    --user-attributes "Name=email,Value=$email" "Name=name,Value=$name" \
    --message-action SUPPRESS >/dev/null 2>&1 || true

  aws cognito-idp admin-set-user-password \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$email" \
    --password "$COGNITO_TEST_PASSWORD" \
    --permanent >/dev/null

  aws cognito-idp admin-add-user-to-group \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$email" \
    --group-name "$group" >/dev/null

  echo "$email -> $group"
}

create_user "${USUARIO_EMAIL:-usuario@demo.sigrif.cl}" usuarios "Usuario demo"
create_user "${OPERADOR_EMAIL:-operador@demo.sigrif.cl}" operadores "Operador demo"
