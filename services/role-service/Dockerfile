FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY common ./common
COPY role-service ./role-service
RUN pip wheel --wheel-dir /wheels ./common ./role-service

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
COPY role-service/main.py role-service/bootstrap_admin.py role-service/alembic.ini role-service/docker-entrypoint.sh ./
COPY role-service/migrations ./migrations

USER appuser
EXPOSE 8000

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
