FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

RUN uv pip install --system --no-cache .

ENV NOMNOM_SERVICE_DB=/data/nomnom.db
VOLUME ["/data"]

EXPOSE 8003

CMD ["uvicorn", "nomnom_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
