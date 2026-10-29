# ============================================================================
# FundFlow Sentinel — Production Dockerfile
# Multi-stage security-hardened container for Streamlit financial intelligence
# ============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final Production Stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Create non-root system user
RUN groupadd -g 1001 fundflow && \
    useradd -u 1001 -g fundflow -m -s /bin/bash fundflow

# Copy installed wheels and binaries from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source code and configuration
COPY --chown=fundflow:fundflow src ./src
COPY --chown=fundflow:fundflow app ./app
COPY --chown=fundflow:fundflow config ./config
COPY --chown=fundflow:fundflow data ./data
COPY --chown=fundflow:fundflow .streamlit ./.streamlit
COPY --chown=fundflow:fundflow scripts ./scripts
COPY --chown=fundflow:fundflow Makefile ./Makefile

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app:/app/src" \
    PORT=8501 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=true \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

USER fundflow

EXPOSE 8501

# Health check probing Streamlit core health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python scripts/healthcheck.py || exit 1

# Launch application
CMD ["streamlit", "run", "app/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
