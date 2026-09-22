# ==============================================================================
# Stage 1: Frontend Build Stage
# ==============================================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

# Install dependencies using clean install
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source and build static distribution
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Backend Runtime Stage
# ==============================================================================
FROM python:3.11-slim AS runner

# System environment variables for Python & 512 MB RAM cloud guard
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    PORT=8000

WORKDIR /app

# Install minimal system utilities for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with zero cache to keep image lean (<300 MB)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for cloud security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy application source code
COPY app/ ./app
COPY main.py ./main.py

# Copy pre-built frontend distribution from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Switch to non-root user
USER appuser

# Expose standard container port
EXPOSE 8000

# Health check probe against API v2 health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v2/health || exit 1

# Start FastAPI application via Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
