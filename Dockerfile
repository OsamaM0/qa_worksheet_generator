# Multi-stage build to protect source code
# Build stage - contains source code and build tools
FROM python:3.10-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for build
WORKDIR /build

# Copy build requirements
COPY requirements.txt setup.py ./
COPY app.py worksheet_generator.py logo.png ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Build wheel package (contains compiled bytecode, no source)
RUN python setup.py bdist_wheel

# Production stage - minimal runtime environment with no source code
FROM python:3.10-slim as production

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    fonts-noto-arabic \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create application directory
WORKDIR /app

# Copy and install the wheel package (no source code included)
COPY --from=builder /build/dist/*.whl /tmp/
COPY --from=builder /build/logo.png /app/
COPY start_app.py /app/

# Create virtual environment and install the wheel
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl /tmp/*.tar.gz

# Set up environment
ENV PYTHONPATH="/app:/opt/venv/lib/python3.10/site-packages"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create temp directory for file operations
RUN mkdir -p /tmp/worksheet_temp && chown -R appuser:appuser /tmp/worksheet_temp
ENV TEMP_DIR=/tmp/worksheet_temp

# Create logs directory
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Make startup script executable
RUN chmod +x /app/start_app.py

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/docs || exit 1

# Expose port
EXPOSE 8081

# Run the application using the minimal startup script
CMD ["python", "/app/start_app.py"]
