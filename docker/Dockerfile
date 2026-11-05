# ==============================================================================
# Multi-stage, unprivileged Dockerfile for GitOps Demo Application
# ==============================================================================

# Stage 1: Build virtual environment with dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies if needed and compile wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Security: create unprivileged system group & user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser

# Copy virtualenv from builder
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv

# Copy application source
COPY --chown=appuser:appgroup app/ /app/

# Environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_NAME="gitops-demo-app" \
    APP_VERSION="v1.0.0" \
    APP_ENV="production" \
    PORT=8080

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; sys_exit = 0 if urllib.request.urlopen('http://localhost:8080/health').getcode() == 200 else 1; exit(sys_exit)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

