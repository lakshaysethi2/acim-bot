# ── Build stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy project metadata + source
COPY pyproject.toml README.md ./
COPY bot.py ./
COPY data/ ./data/

# Install the project
RUN pip install --no-cache-dir --prefix=/install .

# ── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="https://github.com/lakshaysethi2/acim-bot"

# Create a non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code and data, owned by appuser
COPY --chown=appuser:appuser bot.py .
COPY --chown=appuser:appuser data/ data/

# Switch to non-root user
USER appuser

# Health check honours the HEALTH_PORT env var (default 8080)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request,sys; urllib.request.urlopen(f'http://localhost:{int(os.getenv(\"HEALTH_PORT\",\"8080\"))}/health', timeout=3)" || exit 1

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "bot.py"]
