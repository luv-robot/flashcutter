FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY app ./app

ENV FLASHCUTTER_ENVIRONMENT=production
ENV FLASHCUTTER_DATABASE_URL=sqlite:////data/flashcutter.db
ENV FLASHCUTTER_STORAGE_ROOT=/data/storage
ENV FLASHCUTTER_REQUIRE_AUTH=true
ENV FLASHCUTTER_ALLOW_REGISTRATION=true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
