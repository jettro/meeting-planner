.DEFAULT_GOAL := help

SERVICES := meeting-service location-service nomnom-service

.PHONY: help sync lint format typecheck test check \
        run-meeting run-location run-nomnom \
        up down build logs ps clean

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## --- Local development (uv) -------------------------------------------------

sync: ## Install/sync all workspace packages into the shared .venv
	uv sync --all-packages

lint: ## Run ruff checks across all services
	uv run ruff check services

format: ## Auto-format and auto-fix code with ruff
	uv run ruff format services
	uv run ruff check --fix services

typecheck: ## Run mypy across all services
	uv run mypy services

test: ## Run the full pytest suite
	uv run pytest services

check: lint typecheck test ## Run lint + typecheck + test (CI-equivalent)

run-meeting: ## Run meeting-service locally with uv (http://localhost:8001)
	uv run --package meeting-service uvicorn meeting_service.main:app --reload --port 8001

run-location: ## Run location-service locally with uv (http://localhost:8002)
	uv run --package location-service uvicorn location_service.main:app --reload --port 8002

run-nomnom: ## Run nomnom-service locally with uv (http://localhost:8003)
	uv run --package nomnom-service uvicorn nomnom_service.main:app --reload --port 8003

## --- Docker Compose ----------------------------------------------------------

build: ## Build all Docker images
	docker compose build

up: ## Start all services in the background (detached)
	docker compose up -d

down: ## Stop and remove all containers (keep data volumes)
	docker compose down

logs: ## Tail logs from all running containers
	docker compose logs -f

ps: ## Show status of the compose stack
	docker compose ps

clean: ## Stop containers and remove volumes (destroys SQLite data!)
	docker compose down -v
