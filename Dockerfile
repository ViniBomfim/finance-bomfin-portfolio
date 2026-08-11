FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Migrações no render-start.sh; lifespan não repete Alembic
ENV RUN_MIGRATIONS_ON_STARTUP=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic
COPY scripts/render-start.sh ./scripts/render-start.sh
RUN chmod +x ./scripts/render-start.sh

EXPOSE 8000

CMD ["./scripts/render-start.sh"]
