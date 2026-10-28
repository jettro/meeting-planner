FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY catalog ./catalog

RUN uv pip install --system --no-cache .

# The catalog travels with the image; URLs and secrets stay in the environment
# as ${VAR} placeholders, resolved at team-build time (see design_akgents.md §3).
ENV CATALOG_PATH=/app/catalog

# Not a server: one run plans one meeting and exits. Arguments passed to
# `docker compose run agents ...` land straight on the CLI.
ENTRYPOINT ["plan-meeting"]
