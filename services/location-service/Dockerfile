FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

RUN uv pip install --system --no-cache .

ENV LOCATION_SERVICE_DB=/data/location.db
VOLUME ["/data"]

EXPOSE 8002

CMD ["uvicorn", "location_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
