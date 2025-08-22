# Docker Build Troubleshooting Guide

If you're experiencing build failures, try these solutions in order:

## Solution 1: Use Minimal Dockerfile (Recommended)

Edit `docker-compose.yml` and change the dockerfile line:

```yaml
services:
  qa-worksheet-generator:
    build: 
      context: .
      dockerfile: Dockerfile.minimal  # Use this line
```

Then run:
```bash
docker-compose up -d --build
```

## Solution 2: Build with Increased Resources

```bash
# Build with more memory
docker build --memory=4g -t qa-worksheet-generator .

# Or with no cache
docker build --no-cache -t qa-worksheet-generator .
```

## Solution 3: Manual Step-by-Step Build

If automated build fails, try building manually:

```bash
# 1. Pull base image first
docker pull python:3.11-slim

# 2. Build with minimal dockerfile
docker build -f Dockerfile.minimal -t qa-worksheet-generator .

# 3. Run the container
docker run -d --name qa_worksheet_generator -p 8081:8081 qa-worksheet-generator
```

## Solution 4: Use Pre-built Python Image

Create a new Dockerfile with just Python packages:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.docker.txt .
RUN pip install -r requirements.docker.txt
COPY . .
EXPOSE 8081
CMD ["python", "start_app.py"]
```

## Solution 5: Alternative Base Images

If python:3.11-slim fails, try these base images in Dockerfile:

```dockerfile
# Option 1: Ubuntu-based
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3 python3-pip
# ... rest of your dockerfile

# Option 2: Alpine-based (smallest)
FROM python:3.11-alpine
RUN apk add --no-cache curl
# ... rest of your dockerfile

# Option 3: Debian-based
FROM python:3.11-bullseye
# ... rest of your dockerfile
```

## Solution 6: Network Issues

If package downloads fail:

```bash
# Build with different DNS
docker build --build-arg HTTP_PROXY=http://8.8.8.8:53 -t qa-worksheet-generator .

# Or use docker buildx
docker buildx build --platform linux/amd64 -t qa-worksheet-generator .
```

## Solution 7: Check Docker Resources

Ensure Docker has enough resources:

- Memory: At least 4GB
- Disk Space: At least 10GB free
- CPU: 2+ cores recommended

In Docker Desktop:
Settings > Resources > Advanced

## Solution 8: Clean Docker Environment

```bash
# Clean up Docker
docker system prune -a

# Remove all containers and images
docker container prune
docker image prune -a

# Restart Docker service
# Windows: Restart Docker Desktop
# Linux: sudo systemctl restart docker
```

## Solution 9: Use Online Build Services

If local build continues to fail, consider:

1. **GitHub Actions** - Build in the cloud
2. **Docker Hub Automated Builds**
3. **Google Cloud Build**

## Solution 10: Run Without Docker

As a last resort, run directly with Python:

```bash
# Install Python 3.11
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python start_app.py
```

## Quick Test Commands

```bash
# Test if Docker is working
docker run hello-world

# Test Python image
docker run python:3.11-slim python --version

# Test minimal build
docker build -f Dockerfile.minimal -t test-build .

# Check Docker version
docker --version
docker-compose --version
```

## Common Error Solutions

### Error: "exit code: 100"
- Usually package installation failure
- Try minimal Dockerfile
- Check internet connection

### Error: "no space left on device"
- Run `docker system prune -a`
- Increase Docker disk allocation

### Error: "network timeout"
- Check firewall settings
- Try different DNS servers
- Use mobile hotspot as test

### Error: "permission denied"
- Run Docker as administrator (Windows)
- Add user to docker group (Linux)

## Getting Help

If none of these solutions work:

1. Check Docker logs: `docker logs qa_worksheet_generator`
2. Check system resources: `docker system df`
3. Share the exact error message
4. Include Docker version: `docker --version`
5. Include OS information
