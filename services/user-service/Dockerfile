FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY common ./common
COPY user-service ./user-service
RUN pip wheel --wheel-dir /wheels ./common ./user-service

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels

WORKDIR /app
COPY user-service/main.py user-service/alembic.ini user-service/docker-entrypoint.sh ./
COPY user-service/migrations ./migrations

USER appuser
EXPOSE 8000

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
