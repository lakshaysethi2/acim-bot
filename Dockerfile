# ── Build stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="acim-bot"
LABEL description="A Course in Miracles bot for Discord / Telegram"

# Create a non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code and data
COPY bot.py .
COPY data/ data/

# Switch to non-root user
USER appuser

# Health check hits the tiny HTTP server inside the bot
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Signal handling: Python handles SIGTERM/SIGINT in code
STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "bot.py"]
