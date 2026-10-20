#!/usr/bin/env bash
set -euo pipefail

base="${BASE_URL:-http://localhost:8080}"

curl -fsS "$base/health" | grep -q '"status":"ok"'
curl -fsS "$base/api/v1/zones" | grep -q 'SECTOR'
status=$(curl -sS -o /tmp/sigrif_simulate.json -w '%{http_code}' -X POST "$base/api/v1/simulate")
test "$status" = "202"
curl -fsS "$base/api/v1/zones" | grep -q 'risk_level'
echo "smoke ok"
