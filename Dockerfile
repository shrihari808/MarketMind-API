# ==============================================================================
# MarketMind API v2 - Production Backend Runtime (Render Free Tier)
# Strict 512 MB RAM footprint, fast build (<30s), zero Node.js/frontend bloat
# Frontend hosted independently on Vercel: https://market-mind-api.vercel.app
# ==============================================================================
FROM python:3.11-slim

# System environment variables for Python & 512 MB RAM cloud guard
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    PORT=8000

WORKDIR /app

# Install minimal system utilities for healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with zero cache to keep image lean (<150 MB)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for cloud security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy backend application source code
COPY app/ ./app
COPY main.py ./main.py

# Switch to non-root user
USER appuser

# Expose standard container port
EXPOSE 8000

# Health check probe against API v2 health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v2/health || exit 1

# Start FastAPI application via Uvicorn bound dynamically to $PORT (Render / Cloud support)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
