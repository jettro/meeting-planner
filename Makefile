.DEFAULT_GOAL := help

SERVICES := meeting-service location-service nomnom-service

.PHONY: help sync lint format typecheck test check \
        run-meeting run-location run-nomnom \
        run-meeting-mcp run-location-mcp run-nomnom-mcp \
        plan-meeting plan-meeting-docker run-server \
        up down build logs ps clean reset

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## --- Local development (uv) -------------------------------------------------

sync: ## Install/sync all workspace packages into the shared .venv
	uv sync --all-packages

lint: ## Run ruff checks across all services
	uv run ruff check services agents server

format: ## Auto-format and auto-fix code with ruff
	uv run ruff format services agents server
	uv run ruff check --fix services agents server

typecheck: ## Run mypy across all services
	uv run mypy services agents server

test: ## Run the full pytest suite
	uv run pytest services agents server

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

## --- Agent team (akgents) ----------------------------------------------------

# A run on the host reaches the MCP servers on their published ports, while the
# defaults in settings.py name the compose services. Shell variables win over
# `uv run --env-file`, so these override .env without editing it. The API key
# comes from .env and is never echoed here.
AGENT_HOST_ENV := CATALOG_PATH=agents/catalog \
                  PLAN_STORE_PATH=data/plans.json \
                  PYDANTIC_AI_NO_BANNER=1 \
                  MEETING_MCP_URL=http://localhost:8101/mcp \
                  LOCATION_MCP_URL=http://localhost:8102/mcp \
                  NOMNOM_MCP_URL=http://localhost:8103/mcp

plan-meeting: ## Plan a meeting from the terminal; needs `make up`. Pass ARGS="--title ..."
	@$(AGENT_HOST_ENV) uv run --env-file .env --package meeting-agents plan-meeting $(ARGS)

plan-meeting-docker: ## Same, but inside the agents container. Pass ARGS="--title ..."
	docker compose run --rm agents $(ARGS)

# The server reaches the MCP servers and the three APIs on their published
# ports when it runs on the host, exactly as a terminal run does. CORS lets in
# the Vite dev server, which is a different origin by construction.
SERVER_HOST_ENV := $(AGENT_HOST_ENV) \
                   EVENT_STORE_PATH=data/events \
                   WORKSPACES_ROOT=data/workspaces \
                   MEETING_SERVICE_URL=http://localhost:8001 \
                   LOCATION_SERVICE_URL=http://localhost:8002 \
                   NOMNOM_SERVICE_URL=http://localhost:8003 \
                   CORS_ORIGINS=http://localhost:5173

run-server: ## Run the team server on the host (http://localhost:8200); needs `make up`
	@$(SERVER_HOST_ENV) uv run --env-file .env --package meeting-server python -m meeting_server.app

## --- Docker Compose ----------------------------------------------------------

build: ## Build all Docker images (including the agents runner)
	docker compose --profile agents build

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

# Everything the running system has ever written lives in one of three places:
# the named volumes, the SQLite files a local `make run-*` leaves in the repo
# root, and the agents' plan store. Wiping only the volumes leaves a stale
# local database behind, which is confusing precisely when you are trying to
# start clean. The seed data comes back by itself on the next start.
reset: clean ## Wipe ALL data (volumes, local *.db, plan store); stack stays down
	rm -f meeting.db location.db nomnom.db
	rm -f $(foreach s,$(SERVICES),services/$(s)/*.db)
	rm -rf data
	@echo "All data removed. 'make up' starts again from the seed data."
