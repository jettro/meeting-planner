FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

RUN uv pip install --system --no-cache .

ENV MEETING_SERVICE_DB=/data/meeting.db
VOLUME ["/data"]

EXPOSE 8001

CMD ["uvicorn", "meeting_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
