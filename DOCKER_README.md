# QA Worksheet Generator - Docker Setup

This guide explains how to run the QA Worksheet Generator application using Docker.

## 📋 Prerequisites

- Docker installed on your system
- Docker Compose (usually included with Docker Desktop)
- Git (to clone the repository)

## 🚀 Quick Start

### Method 1: Using the provided scripts (Recommended)

**For Windows:**
```bash
# Build the Docker image
build.bat

# Run the application
run.bat
```

**For Linux/macOS:**
```bash
# Make scripts executable
chmod +x build.sh run.sh

# Build the Docker image
./build.sh

# Run the application
./run.sh
```

### Method 2: Using Docker Compose directly

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### Method 3: Using Docker directly

```bash
# Build the image
docker build -t qa-worksheet-generator:latest .

# Run the container
docker run -d \
  --name qa_worksheet_generator \
  -p 8081:8081 \
  -e MONGO_URI="your_mongodb_uri" \
  -e DB_NAME="your_db_name" \
  -v ./logs:/app/logs \
  qa-worksheet-generator:latest
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```env
# MongoDB Configuration
MONGO_URI=mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=ien
DB_NAME=ien

# Server Configuration
HOST=0.0.0.0
PORT=8081
```

### Available Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | See .env.example |
| `DB_NAME` | Database name | `ien` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8081` |

## 🌐 Accessing the Application

Once the container is running, you can access:

- **Main API**: http://localhost:8081
- **API Documentation**: http://localhost:8081/docs
- **Health Check**: http://localhost:8081/docs (will show if the service is healthy)

## 📁 Docker Files Explained

### Dockerfile
- **Base Image**: Python 3.11-slim (secure and lightweight)
- **Dependencies**: 
  - LibreOffice for document conversion
  - Arabic fonts for proper text rendering
  - PDF processing libraries
  - Image processing tools
- **Security**: Runs as non-root user
- **Health Check**: Includes built-in health monitoring

### docker-compose.yml
- **Services**: Main application container
- **Networking**: Isolated network for the application
- **Volumes**: Persistent logs storage
- **Health Checks**: Automatic service monitoring

### .dockerignore
- Excludes unnecessary files from the Docker build context
- Speeds up build process and reduces image size

## 🔍 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using port 8081
   netstat -tulpn | grep 8081
   
   # Change port in .env file or docker-compose.yml
   ```

2. **Permission issues (Linux/macOS)**
   ```bash
   # Make sure scripts are executable
   chmod +x build.sh run.sh
   
   # Fix logs directory permissions
   sudo chown -R $USER:$USER logs/
   ```

3. **Memory issues during build**
   ```bash
   # Build with more memory allocated to Docker
   docker build --memory=4g -t qa-worksheet-generator:latest .
   ```

4. **MongoDB connection issues**
   - Verify `MONGO_URI` in `.env` file
   - Check network connectivity to MongoDB server
   - Ensure MongoDB credentials are correct

### Checking Logs

```bash
# Docker Compose
docker-compose logs -f

# Direct Docker
docker logs qa_worksheet_generator

# Application logs (if volume mounted)
tail -f logs/app.log
```

### Container Management

```bash
# Check container status
docker-compose ps
# or
docker ps | grep qa_worksheet

# Restart container
docker-compose restart
# or
docker restart qa_worksheet_generator

# Stop container
docker-compose down
# or
docker stop qa_worksheet_generator

# Remove container
docker-compose down -v
# or
docker rm qa_worksheet_generator
```

## 🏗️ Development

### Rebuilding After Code Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Or using scripts
./build.sh && ./run.sh
```

### Running Tests in Container

```bash
# Execute tests inside running container
docker exec qa_worksheet_generator python -m pytest

# Or run container specifically for testing
docker run --rm qa-worksheet-generator:latest python -m pytest
```

## 📊 Monitoring

### Health Checks

The container includes built-in health checks that verify:
- Application is responding on port 8081
- API documentation endpoint is accessible

### Resource Usage

```bash
# Monitor resource usage
docker stats qa_worksheet_generator

# Check container details
docker inspect qa_worksheet_generator
```

## 🔐 Security Considerations

- Application runs as non-root user inside container
- Only necessary ports are exposed
- Sensitive configuration in environment variables
- Use official Python base image with regular security updates

## 🤝 Support

If you encounter issues:

1. Check the logs using commands above
2. Verify your `.env` configuration
3. Ensure Docker and Docker Compose are properly installed
4. Check that required ports are available
5. Verify MongoDB connectivity

## 📝 Notes

- The application includes Arabic font support for proper PDF generation
- LibreOffice is included for document conversion capabilities
- Logs are persistent when using Docker Compose
- The container automatically restarts unless stopped manually
