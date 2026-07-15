# syntax=docker/dockerfile:1

# ── Build stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install third-party dependencies before copying application files. This layer
# is reused when bot.py or data files change and is invalidated only when the
# project metadata (and therefore potentially its dependencies) changes.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python - <<'PY'
import subprocess
import sys
import tomllib

with open("pyproject.toml", "rb") as config:
    dependencies = tomllib.load(config)["project"]["dependencies"]

subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "--prefix=/install", *dependencies]
)
PY

# ── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="https://github.com/lakshaysethi2/acim-bot"

# Create a non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Keep frequently changed application files in the final layers so changing a
# JSON data file does not trigger dependency installation.
COPY --chown=appuser:appuser bot.py .
COPY --chown=appuser:appuser data/ data/

# Switch to non-root user
USER appuser

# Health check honours the HEALTH_PORT env var (default 8080)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request,sys; urllib.request.urlopen(f'http://localhost:{int(os.getenv(\"HEALTH_PORT\",\"8080\"))}/health', timeout=3)" || exit 1

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "bot.py"]
