.DEFAULT_GOAL := help

SERVICES := meeting-service location-service nomnom-service

.PHONY: help sync lint format typecheck test check \
        run-meeting run-location run-nomnom \
        run-meeting-mcp run-location-mcp run-nomnom-mcp \
        up down build logs ps clean

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## --- Local development (uv) -------------------------------------------------

sync: ## Install/sync all workspace packages into the shared .venv
	uv sync --all-packages

lint: ## Run ruff checks across all services
	uv run ruff check services agents

format: ## Auto-format and auto-fix code with ruff
	uv run ruff format services agents
	uv run ruff check --fix services agents

typecheck: ## Run mypy across all services
	uv run mypy services agents

test: ## Run the full pytest suite
	uv run pytest services agents

check: lint typecheck test ## Run lint + typecheck + test (CI-equivalent)

run-meeting: ## Run meeting-service locally with uv (http://localhost:8001)
	uv run --package meeting-service uvicorn meeting_service.main:app --reload --port 8001

run-location: ## Run location-service locally with uv (http://localhost:8002)
	uv run --package location-service uvicorn location_service.main:app --reload --port 8002

run-nomnom: ## Run nomnom-service locally with uv (http://localhost:8003)
	uv run --package nomnom-service uvicorn nomnom_service.main:app --reload --port 8003

run-meeting-mcp: ## Run meeting-service's MCP server locally with uv (http://localhost:8101/mcp)
	uv run --package meeting-service uvicorn meeting_service.mcp_server:mcp_app --reload --port 8101

run-location-mcp: ## Run location-service's MCP server locally with uv (http://localhost:8102/mcp)
	uv run --package location-service uvicorn location_service.mcp_server:mcp_app --reload --port 8102

run-nomnom-mcp: ## Run nomnom-service's MCP server locally with uv (http://localhost:8103/mcp)
	uv run --package nomnom-service uvicorn nomnom_service.mcp_server:mcp_app --reload --port 8103

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
