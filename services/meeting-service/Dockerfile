FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY entrypoint.sh ./

RUN uv pip install --system --no-cache . \
    && chmod +x entrypoint.sh

ENV MEETING_SERVICE_DB=/data/meeting.db
VOLUME ["/data"]

# 8001 = REST + UI, 8101 = MCP (agent-facing tools, see design.md section 3)
EXPOSE 8001 8101

CMD ["./entrypoint.sh"]
