# Multi-stage Dockerfile for production
FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    ca-certificates \
    apt-transport-https \
    unixodbc-dev \
    build-essential \
    && mkdir -p /usr/share/keyrings \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy and install Python dependencies
COPY docker/requirements-docker.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only what's needed for API server)
COPY api/ ./api/
COPY app/ ./app/
COPY database/ ./database/

# Create necessary directories
RUN mkdir -p logs/api files && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

EXPOSE 8008

CMD ["python", "-m", "api.server"]