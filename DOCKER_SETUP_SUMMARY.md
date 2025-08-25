# Docker Setup Summary - Saudi Edu Worksheet Generator

## Overview
The Docker setup has been optimized for production deployment with S3 integration and robust PDF conversion capabilities on Linux servers.

## Key Improvements Made

### 1. Consolidated Docker Configuration
- **Single Dockerfile**: Removed `Dockerfile.pdf-optimized`, now using one unified `Dockerfile`
- **Optimized for Linux**: Focused on LibreOffice + unoconv for reliable PDF conversion
- **Multi-stage build**: Separates build dependencies from runtime for smaller images
- **S3 Integration**: Full Cloudflare R2 support built-in

### 2. Requirements Optimization
- **Unified requirements.txt**: Removed `requirements.docker.txt` redundancy
- **Production-focused**: Removed development dependencies
- **Platform-specific**: Windows-only packages conditional on platform
- **S3 libraries**: boto3 included for cloud storage

### 3. Docker Compose Configuration
- **Removed obsolete version field**: Now uses modern Docker Compose format
- **S3 environment variables**: Complete R2 configuration support
- **Optimized health checks**: Simplified and more reliable
- **Resource limits**: Appropriate for PDF conversion workloads

### 4. Removed Unused Files
The following files were removed as they are no longer needed:
- `Dockerfile.pdf-optimized` (consolidated into main Dockerfile)
- `requirements.docker.txt` (merged into requirements.txt)
- `start_app_enhanced.py` (main start_app.py is sufficient)
- `build_with_pdf.bat` (Windows batch file, not needed for Linux)
- `deploy.bat` (Windows batch file, not needed for Linux)
- `example_s3_usage.py` (S3 is now integrated in main app)
- `setup.py` (using Docker deployment)

### 5. Enhanced Deployment
- **Comprehensive deploy.sh**: Full deployment automation with health checks
- **PDF conversion testing**: Built-in test script for verification
- **Improved .dockerignore**: Excludes unnecessary files for faster builds

## Current File Structure
```
qa_worksheet_generator/
├── .dockerignore          # Optimized Docker build exclusions
├── .env                   # Environment variables (includes S3 config)
├── app.py                 # Main FastAPI application with S3 integration
├── build_with_pdf.sh      # Build script (keep for manual builds)
├── deploy.sh              # Production deployment script
├── docker-compose.yml     # Single, optimized compose configuration
├── Dockerfile             # Unified, production-ready Dockerfile
├── logo.png               # Application logo for watermarks
├── requirements.txt       # Consolidated Python dependencies
├── s3_service.py          # S3/Cloudflare R2 service implementation
├── start_app.py           # Application startup script
├── test_pdf_conversion.py # PDF conversion test suite
├── test_s3_service.py     # S3 service testing
└── worksheet_generator.py # Core worksheet generation logic
```

## Docker Configuration Details

### Dockerfile Features
- **Base Image**: Python 3.11-slim for security and size
- **Multi-stage build**: Build stage + runtime stage
- **PDF Tools**: LibreOffice, unoconv, comprehensive fonts
- **Arabic Support**: Noto fonts, Arabic reshaper, bidirectional text
- **Security**: Non-root user, minimal attack surface
- **Health Checks**: Built-in application health monitoring

### Docker Compose Features
- **Environment Variables**: Complete S3 and MongoDB configuration
- **Volume Mounts**: Persistent logs and temp file handling
- **Network Isolation**: Dedicated network for the application
- **Resource Limits**: Memory and CPU limits appropriate for PDF processing
- **Restart Policy**: Automatic restart on failures

### S3 Integration
The application now includes:
- **Automatic Upload**: Generated files automatically uploaded to S3/R2
- **Public URLs**: Direct access to uploaded files
- **Health Monitoring**: S3 service status endpoint
- **Error Handling**: Graceful fallback if S3 is unavailable

## PDF Conversion Optimization

### Linux-Optimized Approach
1. **Primary**: unoconv (fastest, most reliable on Linux)
2. **Fallback**: Direct LibreOffice CLI
3. **Fonts**: Comprehensive font installation for Arabic support
4. **Watermarking**: Logo overlay using ReportLab

### Testing
Use the included test script:
```bash
docker exec -it qa_worksheet_generator python test_pdf_conversion.py
```

## Deployment Commands

### Quick Start
```bash
# Clone and deploy
git clone <repository>
cd qa_worksheet_generator
./deploy.sh
```

### Manual Deployment
```bash
# Build image
docker build -t saudi-edu-worksheet-generator .

# Run with docker-compose
docker-compose up -d

# Or run directly
docker run -d --name qa_worksheet_generator -p 8081:8081 \
  --env-file .env saudi-edu-worksheet-generator
```

### Management
```bash
# View logs
docker logs -f qa_worksheet_generator

# Check health
curl http://localhost:8081/docs
curl http://localhost:8081/pdf-status/
curl http://localhost:8081/s3-status/

# Stop/start
docker-compose down
docker-compose up -d
```

## Environment Variables

### Required for S3
```env
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_ENDPOINT=https://your-account.r2.cloudflarestorage.com
S3_BUCKET_NAME=your_bucket_name
```

### Optional
```env
MONGO_URI=mongodb://user:pass@host:port/db
DB_NAME=database_name
DEBUG=false
LOG_LEVEL=INFO
```

## API Endpoints

### Core Functionality
- `GET /docs` - API documentation
- `GET /generate-worksheet/` - Main worksheet generation
- `GET /search-lessons/` - Search for lessons
- `GET /lesson-details/{id}` - Lesson information

### Monitoring
- `GET /pdf-status/` - PDF conversion status
- `GET /s3-status/` - S3 service health
- `GET /list-files/` - List uploaded files
- `GET /download/{file_key}` - Download files from S3

## Performance Optimization

### Resource Allocation
- **Memory**: 2GB limit (1GB for LibreOffice, 1GB for app)
- **CPU**: 1 core limit with 0.5 core reservation
- **Storage**: Temp files automatically cleaned up

### PDF Conversion
- **Timeout**: 60 seconds per conversion
- **Retries**: 3 attempts with different methods
- **Parallelization**: Can handle multiple requests simultaneously

## Security Considerations

### Container Security
- **Non-root user**: Application runs as unprivileged user
- **Minimal base**: Python slim image reduces attack surface
- **Read-only mounts**: Logo file mounted read-only
- **Network isolation**: Application runs in dedicated network

### Data Security
- **Environment variables**: Sensitive data in .env file
- **Temporary files**: Automatic cleanup after processing
- **S3 uploads**: Secure authenticated uploads to private bucket

## Troubleshooting

### Common Issues
1. **PDF conversion fails**: Check `test_pdf_conversion.py` output
2. **S3 upload fails**: Verify credentials in `/s3-status/`
3. **High memory usage**: Adjust resource limits in docker-compose.yml
4. **Slow startup**: Wait for LibreOffice initialization (90 seconds)

### Debug Commands
```bash
# Shell access
docker exec -it qa_worksheet_generator /bin/bash

# Test PDF tools
docker exec -it qa_worksheet_generator libreoffice --version
docker exec -it qa_worksheet_generator unoconv --version

# Test Python imports
docker exec -it qa_worksheet_generator python -c "import boto3; print('S3 OK')"
```

## Production Readiness Checklist

- ✅ Single optimized Dockerfile
- ✅ Consolidated requirements
- ✅ S3 integration tested
- ✅ PDF conversion verified
- ✅ Health checks implemented
- ✅ Resource limits configured
- ✅ Security hardening applied
- ✅ Automated deployment script
- ✅ Comprehensive monitoring
- ✅ Error handling and fallbacks

The Docker setup is now production-ready with robust PDF conversion capabilities and seamless S3 integration for Linux deployment.
