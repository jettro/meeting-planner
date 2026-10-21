FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY entrypoint.sh ./

RUN uv pip install --system --no-cache . \
    && chmod +x entrypoint.sh

ENV NOMNOM_SERVICE_DB=/data/nomnom.db
VOLUME ["/data"]

# 8003 = REST + UI, 8103 = MCP (agent-facing tools, see design.md section 3)
EXPOSE 8003 8103

CMD ["./entrypoint.sh"]
