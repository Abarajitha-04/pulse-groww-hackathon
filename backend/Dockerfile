# Multi-stage build: the builder installs into a virtualenv so the final
# image doesn't carry pip's cache, build toolchains, or wheel files.
FROM python:3.12-slim AS builder

WORKDIR /build

# psycopg2-binary needs libpq at runtime but build tools only during
# `pip install` — keeping this in the builder stage keeps the final image
# smaller than installing build-essential in the runtime stage too.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

# libpq5 is the runtime-only counterpart to libpq-dev above.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/false pulse

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --chown=pulse:pulse . .

USER pulse

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Migrations run as a separate deploy step (see docs/DEPLOYMENT.md and
# docker-compose.yml's `migrate` service) rather than baked into this
# CMD — running `alembic upgrade head` as part of every container start
# means N replicas race to apply the same migration concurrently.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
