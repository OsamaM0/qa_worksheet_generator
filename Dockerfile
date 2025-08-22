# Use Python 3.11 slim image as base (more recent and secure)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8081

# Set work directory
WORKDIR /app

# Install system dependencies for document processing and Arabic text support
RUN apt-get update && apt-get install -y \
    # Basic system tools
    curl \
    wget \
    git \
    # Document processing dependencies
    libreoffice \
    fonts-liberation \
    fonts-dejavu \
    fonts-noto \
    # Arabic fonts for proper text rendering
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    fonts-arabic \
    # Image processing dependencies
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    zlib1g-dev \
    # PDF processing dependencies
    libpoppler-cpp-dev \
    poppler-utils \
    # Build tools (needed for some Python packages)
    build-essential \
    gcc \
    g++ \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create logs directory
RUN mkdir -p /app/logs

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Create virtual environment and install Python dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure the logo file exists (copy if available)
RUN if [ ! -f logo.png ]; then \
    echo "Warning: logo.png not found, creating placeholder"; \
    touch logo.png; \
    fi

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Change ownership of the app directory and logs
RUN chown -R appuser:appuser /app /opt/venv

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8081/docs || exit 1

# Set the Python path to include the virtual environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Run the application
CMD ["python", "start_app.py"]
