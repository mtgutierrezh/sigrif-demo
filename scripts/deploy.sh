#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/infra"

terraform init -input=false
terraform apply -auto-approve -input=false \
  -target=aws_ecr_repository.backend \
  -target=aws_ecr_repository.nginx

region="$(terraform output -raw aws_region)"
backend_repo="$(terraform output -raw backend_repository_url)"
nginx_repo="$(terraform output -raw nginx_repository_url)"

aws ecr get-login-password --region "$region" \
  | docker login --username AWS --password-stdin "${backend_repo%%/*}"

docker build -t "$backend_repo:latest" "$root"
docker build -t "$nginx_repo:latest" "$root/nginx"
docker push "$backend_repo:latest"
docker push "$nginx_repo:latest"

terraform apply -auto-approve -input=false

cluster="$(terraform output -raw cluster_name)"
for service in api ia nginx; do
  aws ecs update-service --cluster "$cluster" --service "$service" \
    --force-new-deployment --region "$region" >/dev/null
done

aws ecs wait services-stable --cluster "$cluster" --services api ia nginx --region "$region"
