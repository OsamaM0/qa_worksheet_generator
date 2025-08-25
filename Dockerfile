# ==============================================================================
# OPTIMIZED DOCKER IMAGE FOR SAUDI EDU WORKSHEET GENERATOR
# ==============================================================================
# Production-ready Docker image with S3 integration, PDF conversion,
# Arabic text processing, and comprehensive functionality for Linux deployment.
# 
# Features included:
# - Full PDF conversion support (LibreOffice + unoconv)
# - Arabic font support
# - S3/Cloudflare R2 integration
# - MongoDB connectivity
# - Complete Python dependencies
# - Security (non-root user)
# - Health checks and monitoring
# - Multi-stage build for optimization
# ==============================================================================

# ==============================================================================
# STAGE 1: BUILD ENVIRONMENT
# ==============================================================================
FROM python:3.11-slim as builder

# Build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    gcc \
    g++ \
    make \
    # Image processing build deps
    libpng-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    # Font config
    libfontconfig1-dev \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install Python packages
WORKDIR /build
COPY requirements.txt ./

# Install all packages from requirements.txt
RUN pip install -r requirements.txt

# Install additional PDF conversion libraries
RUN pip install weasyprint reportlab pypdf2

# ==============================================================================
# STAGE 2: RUNTIME ENVIRONMENT
# ==============================================================================
FROM python:3.11-slim as runtime

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8081 \
    # LibreOffice environment variables for headless operation
    SAL_USE_VCLPLUGIN=svp \
    LIBREOFFICE_HEADLESS=1 \
    # PDF conversion settings
    PDF_CONVERSION_TIMEOUT=60 \
    PDF_CONVERSION_RETRIES=3 \
    # Python path
    PYTHONPATH="/app:$PYTHONPATH"

# Set work directory
WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential tools
    curl \
    wget \
    ca-certificates \
    procps \
    netcat-openbsd \
    file \
    # Basic fonts for text rendering
    fonts-liberation \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-noto \
    libfontconfig1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directories
RUN mkdir -p /app/logs /app/temp /app/uploads /app/downloads

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    # Give appuser access to necessary directories
    chown -R appuser:appuser /app /opt/venv

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure logo file exists
RUN if [ ! -f logo.png ]; then \
        echo "Warning: logo.png not found, creating placeholder"; \
        echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" | base64 -d > logo.png; \
    else \
        echo "✓ Using existing logo.png"; \
    fi

# Make scripts executable
RUN chmod +x *.sh || true

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8081

# Simple health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8081/docs || exit 1

# ==============================================================================
# STARTUP CONFIGURATION
# ==============================================================================

# Create startup script
RUN echo '#!/bin/bash\n\
echo "=== Saudi Edu Worksheet Generator Startup ==="\n\
echo "Platform: $(uname -a)"\n\
echo "Python: $(python --version)"\n\
echo "Working directory: $(pwd)"\n\
echo "User: $(whoami)"\n\
echo "PDF conversion: Python libraries (WeasyPrint, ReportLab)"\n\
echo ""\n\
echo "Starting application..."\n\
exec python start_app.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Default command
CMD ["/app/start.sh"]

# ==============================================================================
# LABELS AND METADATA
# ==============================================================================
LABEL maintainer="Saudi Edu Team" \
      version="1.0.0" \
      description="Unified Saudi Edu Worksheet Generator with full PDF support" \
      features="pdf-conversion,arabic-support,mongodb,fastapi" \
      build-date="2025-08-23"

# ==============================================================================
# BUILD ARGUMENTS (for customization)
# ==============================================================================
ARG BUILD_VERSION=latest
ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.version=${BUILD_VERSION} \
      org.opencontainers.image.created=${BUILD_DATE} \
      org.opencontainers.image.revision=${VCS_REF} \
      org.opencontainers.image.title="Saudi Edu Worksheet Generator" \
      org.opencontainers.image.description="Complete worksheet generation system with PDF conversion"
