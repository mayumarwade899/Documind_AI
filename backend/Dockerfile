# Multi-stage Dockerfile for DocumentMind AI Backend
# Optimized for Railway deployment and minimal image size

# ============================================================================
# BUILD STAGE: Install dependencies
# ============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies (only in builder stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install in temporary location
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ============================================================================
# RUNTIME STAGE: Minimal production image
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Update PATH to use user-installed packages
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Copy application code
COPY . .

# Create required data directories with proper permissions
RUN mkdir -p data/chroma_db data/bm25_index data/documents \
    data/golden_dataset data/metrics data/feedback data/logs \
    data/evaluation_reports && \
    chmod -R 755 data

# Expose API port
EXPOSE 8000

# Health check with timeout
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run uvicorn with production settings
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
