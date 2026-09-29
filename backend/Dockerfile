# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Dependencies are installed from the lockfile alone, so this layer is reused
# for as long as the lockfile is unchanged.
FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache --no-install-project

FROM deps AS app
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --frozen --no-dev --no-cache

ARG VERSION=dev
ARG COMMIT_SHA=unknown
ARG BUILD_TIME=unknown
ENV VERSION=${VERSION} COMMIT_SHA=${COMMIT_SHA} BUILD_TIME=${BUILD_TIME}
ENV PATH="/app/.venv/bin:${PATH}"

LABEL org.opencontainers.image.title="ai-task-bot" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_TIME}"

USER app
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Model is baked in at build time so the first request doesn't pay for the
# download, and the image still works with no network access at runtime.
FROM app AS worker
USER root
RUN uv sync --frozen --no-dev --no-cache --extra worker
ENV HF_HOME=/home/app/.cache/huggingface
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', compute_type='int8')" \
    && chown -R app:app /home/app/.cache
USER app
