FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY entrypoint.sh ./

RUN uv pip install --system --no-cache . \
    && chmod +x entrypoint.sh

ENV LOCATION_SERVICE_DB=/data/location.db
VOLUME ["/data"]

# 8002 = REST + UI, 8102 = MCP (agent-facing tools, see design.md section 3)
EXPOSE 8002 8102

CMD ["./entrypoint.sh"]
