#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

: "${BACKEND_IMAGE:?Falta BACKEND_IMAGE}"
: "${NGINX_IMAGE:?Falta NGINX_IMAGE}"

OUT=${1:-dist/sigrif-deploy.tar.gz}
BUNDLE=build/deploy-bundle

rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/scripts" "$(dirname "$OUT")"

cp docker-compose.prod.yml "$BUNDLE/"
cp -R observability "$BUNDLE/"
cp scripts/deploy_remote.sh scripts/bluegreen_deploy.sh scripts/init_letsencrypt.sh "$BUNDLE/scripts/"

cat > "$BUNDLE/images.env" <<EOF
BACKEND_IMAGE=$BACKEND_IMAGE
NGINX_IMAGE=$NGINX_IMAGE
EOF

tar -czf "$OUT" -C "$BUNDLE" .
echo "Bundle listo: $OUT"
