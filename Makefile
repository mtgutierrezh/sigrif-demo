.PHONY: install up up-host down down-host logs logs-host seed seed-host smoke demo-local test test-e2e lint typecheck fmt security verify check-no-comments train train-fast demo-up demo-down demo-plan demo-status demo-url infra-fmt free-plan free-up free-down free-fmt publish-model deploy-bundle

install:
	uv sync --all-groups

up:
	docker compose up --build -d --wait --wait-timeout 120

up-host:
	docker compose -f docker-compose.host.yml up --build -d --wait --wait-timeout 120

down:
	docker compose down -v

down-host:
	docker compose -f docker-compose.host.yml down -v

logs:
	docker compose logs -f

logs-host:
	docker compose -f docker-compose.host.yml logs -f

seed:
	docker compose run --rm api python -m sigrif.worker.main

seed-host:
	docker compose -f docker-compose.host.yml run --rm api python -m sigrif.worker.main

smoke:
	bash scripts/smoke.sh

demo-local: up-host seed-host smoke

train:
	uv run python scripts/train_model.py --cross-validate

train-fast:
	uv run python scripts/train_model.py

test:
	uv run pytest

test-e2e:
	SIGRIF_E2E=1 uv run pytest tests/test_e2e.py -q --no-cov

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy src

fmt:
	uv run ruff format src tests

security:
	uv run bandit -q -r src
	uv run pip-audit

check-no-comments:
	uv run python scripts/check_no_comments.py

verify: lint typecheck test security check-no-comments

demo-up:
	bash scripts/deploy.sh

demo-down:
	bash scripts/destroy.sh

demo-status:
	cd infra && terraform output

demo-url:
	bash scripts/demo_url.sh

demo-plan:
	cd infra && terraform init -input=false && terraform plan

infra-fmt:
	terraform fmt -recursive infra

free-plan:
	cd infra/free-tier && terraform init -input=false && terraform plan

free-up:
	cd infra/free-tier && terraform init -input=false && terraform apply

free-down:
	cd infra/free-tier && terraform destroy

free-fmt:
	terraform fmt -recursive infra/free-tier

publish-model:
	@test -n "$(BUCKET)" || (echo "Uso: make publish-model BUCKET=mi-bucket" && exit 1)
	bash scripts/publish_model.sh "$(BUCKET)"

deploy-bundle:
	@test -n "$(BACKEND_IMAGE)" || (echo "Falta BACKEND_IMAGE" && exit 1)
	@test -n "$(NGINX_IMAGE)" || (echo "Falta NGINX_IMAGE" && exit 1)
	bash scripts/package_deploy.sh
