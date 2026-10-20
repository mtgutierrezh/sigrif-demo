.PHONY: install up up-host down down-host logs logs-host seed seed-host smoke demo-local test lint fmt security verify check-no-comments demo-up demo-down demo-plan demo-status demo-url infra-fmt

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

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

fmt:
	uv run ruff format src tests

security:
	uv run bandit -q -r src
	uv run pip-audit

check-no-comments:
	uv run python scripts/check_no_comments.py

verify: lint test security check-no-comments

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
