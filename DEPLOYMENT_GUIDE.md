# 🚀 Complete Deployment Guide - Saudi Edu Worksheet Generator

## 📋 Overview

This guide covers deploying the unified Docker image that includes all features:
- ✅ Full PDF conversion support (LibreOffice + unoconv)
- ✅ Arabic text and font support
- ✅ Complete Python dependencies
- ✅ Security and performance optimizations
- ✅ Health monitoring and diagnostics

## 🏗️ Quick Start

### 1. Build the Unified Image

```bash
# Linux/Mac
chmod +x build_with_pdf.sh
./build_with_pdf.sh

# Windows
build_with_pdf.bat

# Or manually:
docker build -t worksheet-generator .
```

### 2. Run with Docker

```bash
# Simple run
docker run -p 8081:8081 worksheet-generator

# With environment variables
docker run -p 8081:8081 \
  -e MONGO_URI="your_mongo_connection_string" \
  -e DB_NAME="your_database_name" \
  worksheet-generator
```

### 3. Run with Docker Compose

```bash
# Start the application
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop the application
docker-compose down
```

## 🔧 Configuration

### Environment Variables

```bash
# Database Configuration
MONGO_URI=mongodb://user:pass@host:port/db?authSource=db
DB_NAME=your_database

# Application Settings
HOST=0.0.0.0
PORT=8081
LOG_LEVEL=INFO

# PDF Conversion Settings
SAL_USE_VCLPLUGIN=svp
LIBREOFFICE_HEADLESS=1
PDF_CONVERSION_TIMEOUT=60
PDF_CONVERSION_RETRIES=3

# Feature Toggles
PDF_CONVERSION_AVAILABLE=true
ENABLE_PDF_WATERMARK=true
```

### Docker Compose Configuration

```yaml
version: '3.8'
services:
  qa-worksheet-generator:
    image: worksheet-generator:latest
    ports:
      - "8081:8081"
    environment:
      - MONGO_URI=${MONGO_URI}
      - DB_NAME=${DB_NAME}
      - PDF_CONVERSION_AVAILABLE=true
    volumes:
      - ./logs:/app/logs
      - ./temp:/app/temp
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

## 🧪 Testing and Verification

### 1. Basic Health Check

```bash
# Check if application is running
curl http://localhost:8081/docs

# Check PDF conversion status
curl http://localhost:8081/pdf-status/
```

### 2. PDF Conversion Test

```bash
# Run comprehensive PDF test
docker run --rm worksheet-generator python test_pdf_conversion.py

# Or inside running container
docker exec -it qa_worksheet_generator python test_pdf_conversion.py
```

### 3. API Functionality Test

```bash
# Test worksheet generation
curl -X POST "http://localhost:8081/generate-worksheet/" \
  -H "Content-Type: application/json" \
  -d '{
    "lesson_id": "test_lesson",
    "generate_pdf": true,
    "num_questions": 5
  }'
```

## 🏭 Production Deployment

### 1. Server Requirements

**Minimum:**
- 2 CPU cores
- 2GB RAM
- 10GB disk space
- Ubuntu 20.04+ or similar

**Recommended:**
- 4 CPU cores
- 4GB RAM
- 20GB disk space
- Load balancer for multiple instances

### 2. Production Docker Compose

```yaml
version: '3.8'
services:
  qa-worksheet-generator:
    image: worksheet-generator:latest
    ports:
      - "8081:8081"
    environment:
      - MONGO_URI=${MONGO_URI}
      - DB_NAME=${DB_NAME}
      - LOG_LEVEL=INFO
      - PDF_CONVERSION_AVAILABLE=true
    volumes:
      - /var/log/worksheet-generator:/app/logs
      - /tmp/worksheet-temp:/app/temp
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/docs"]
      interval: 60s
      timeout: 30s
      retries: 3
      start_period: 90s
    networks:
      - worksheet-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - qa-worksheet-generator
    networks:
      - worksheet-network

networks:
  worksheet-network:
    driver: bridge
```

### 3. Nginx Configuration

```nginx
upstream worksheet_backend {
    server qa-worksheet-generator:8081;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://worksheet_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for PDF generation
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

## 📊 Monitoring and Logging

### 1. Health Monitoring

```bash
# Monitor container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check application logs
docker logs -f qa_worksheet_generator

# Monitor resource usage
docker stats qa_worksheet_generator
```

### 2. Log Management

```bash
# View logs
docker-compose logs -f qa-worksheet-generator

# Log rotation (add to logrotate)
/var/log/worksheet-generator/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

### 3. Performance Metrics

```bash
# Check PDF conversion performance
curl http://localhost:8081/pdf-status/

# Monitor API response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8081/docs
```

## 🔍 Troubleshooting

### Common Issues

1. **PDF Conversion Fails**
   ```bash
   # Check PDF tools
   docker exec -it qa_worksheet_generator libreoffice --version
   docker exec -it qa_worksheet_generator unoconv --version
   
   # Run diagnostic
   docker exec -it qa_worksheet_generator python test_pdf_conversion.py
   ```

2. **Memory Issues**
   ```bash
   # Increase Docker memory
   docker-compose up -d --scale qa-worksheet-generator=1
   
   # Check memory usage
   docker stats --no-stream
   ```

3. **Slow Performance**
   ```bash
   # Check resource limits
   docker inspect qa_worksheet_generator | grep -A 10 "Memory"
   
   # Scale horizontally
   docker-compose up -d --scale qa-worksheet-generator=2
   ```

### Debug Mode

```bash
# Run with debug logging
docker run -p 8081:8081 \
  -e LOG_LEVEL=DEBUG \
  -e PDF_CONVERSION_DEBUG=true \
  worksheet-generator

# Interactive debugging
docker run -it --entrypoint /bin/bash worksheet-generator
```

## 🔐 Security Considerations

### 1. Environment Variables

```bash
# Use Docker secrets or external secret management
docker secret create mongo_uri /path/to/mongo_uri.txt

# Use .env file for local development only
echo "MONGO_URI=mongodb://..." > .env.local
```

### 2. Network Security

```yaml
# Restrict network access
services:
  qa-worksheet-generator:
    networks:
      - internal
    expose:
      - "8081"  # Don't publish to host
```

### 3. User Permissions

```bash
# The unified Dockerfile already runs as non-root user
# Verify user in container
docker exec -it qa_worksheet_generator whoami
# Should output: appuser
```

## 📈 Scaling and Performance

### Horizontal Scaling

```yaml
services:
  qa-worksheet-generator:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

### Load Balancing

```bash
# Using HAProxy or nginx upstream
upstream worksheet_pool {
    server container1:8081;
    server container2:8081;
    server container3:8081;
}
```

## 🚀 CI/CD Integration

### GitHub Actions

```yaml
name: Build and Deploy
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build Docker image
        run: docker build -t worksheet-generator .
      - name: Test PDF conversion
        run: docker run --rm worksheet-generator python test_pdf_conversion.py
      - name: Deploy to production
        run: docker-compose up -d
```

## 📝 Maintenance

### Regular Tasks

```bash
# Update the image
docker pull worksheet-generator:latest
docker-compose up -d

# Clean up old images
docker image prune -f

# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz ./logs/

# Monitor disk usage
df -h
du -sh ./logs/ ./temp/
```

### Updates and Patches

```bash
# Update application
git pull origin main
docker build -t worksheet-generator:latest .
docker-compose up -d --no-deps qa-worksheet-generator

# Verify update
curl http://localhost:8081/pdf-status/
```

## 📞 Support

If you encounter issues:

1. **Check the logs**: `docker-compose logs -f`
2. **Run diagnostics**: `docker exec -it qa_worksheet_generator python test_pdf_conversion.py`
3. **Verify PDF status**: `curl http://localhost:8081/pdf-status/`
4. **Check resources**: `docker stats --no-stream`

For additional support, provide:
- Output of diagnostic script
- Docker logs
- System specifications
- Error messages
