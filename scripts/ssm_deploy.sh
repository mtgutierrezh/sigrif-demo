#!/bin/bash
set -euo pipefail

: "${1:?Uso: ssm_deploy.sh <instance_id> <bucket> <key> [region]}"
: "${2:?Falta el bucket}"
: "${3:?Falta la clave del bundle}"

INSTANCE_ID=$1
BUCKET=$2
KEY=$3
REGION=${4:-us-east-2}

REMOTE_COMMAND=$(cat <<EOF
set -euo pipefail
aws s3 cp s3://$BUCKET/$KEY /tmp/sigrif-deploy.tar.gz --region $REGION
rm -rf /opt/sigrif/release
mkdir -p /opt/sigrif/release
tar -xzf /tmp/sigrif-deploy.tar.gz -C /opt/sigrif/release
cd /opt/sigrif/release
bash scripts/deploy_remote.sh
EOF
)

PARAMETERS=$(python3 -c \
  'import json, sys; print(json.dumps({"commands": [sys.argv[1]]}))' \
  "$REMOTE_COMMAND")

COMMAND_ID=$(aws ssm send-command \
  --document-name AWS-RunShellScript \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --timeout-seconds 1800 \
  --comment "SIGRIF deploy $KEY" \
  --parameters "$PARAMETERS" \
  --query 'Command.CommandId' \
  --output text)

echo "Comando SSM: $COMMAND_ID"
aws ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION"

STATUS=$(aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query Status \
  --output text)

aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query StandardOutputContent \
  --output text

if [ "$STATUS" != "Success" ]; then
  echo "El despliegue terminó con estado $STATUS" >&2
  exit 1
fi
