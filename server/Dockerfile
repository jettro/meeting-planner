# The server needs two workspace members - the agents package and its own - so
# the build context is the repository root rather than this directory. The
# other members' `pyproject.toml` files are copied because uv has to see the
# whole workspace to resolve the lock; their sources are not, because
# `--package meeting-server` never builds them.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install into the image's own Python rather than a virtualenv, so the
# entry point works without an activation step.
ENV UV_PROJECT_ENVIRONMENT=/usr/local

COPY pyproject.toml uv.lock ./
COPY services/meeting-service/pyproject.toml services/meeting-service/
COPY services/location-service/pyproject.toml services/location-service/
COPY services/nomnom-service/pyproject.toml services/nomnom-service/
COPY agents/pyproject.toml agents/
COPY agents/src agents/src
COPY server/pyproject.toml server/
COPY server/src server/src

RUN uv sync --frozen --no-dev --package meeting-server

# The catalog travels with the image; URLs and keys stay in the environment as
# ${VAR} placeholders, resolved when a team is built (design_akgents.md §3).
COPY agents/catalog ./catalog

ENV CATALOG_PATH=/app/catalog
ENV PLAN_STORE_PATH=/data/plans.json
ENV EVENT_STORE_PATH=/data/events
ENV WORKSPACES_ROOT=/data/workspaces
VOLUME ["/data"]

EXPOSE 8200

CMD ["python", "-m", "meeting_server.app"]
