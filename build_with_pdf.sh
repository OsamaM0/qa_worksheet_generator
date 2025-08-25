#!/bin/bash
# ==============================================================================
# UNIFIED BUILD SCRIPT FOR SAUDI EDU WORKSHEET GENERATOR
# ==============================================================================
# This script builds the unified Docker image with all features including
# PDF conversion, Arabic support, and comprehensive functionality.

set -e  # Exit on any error

# Configuration
IMAGE_NAME="worksheet-generator"
VERSION="${BUILD_VERSION:-latest}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}Saudi Edu Worksheet Generator Builder${NC}"
echo -e "${BLUE}Unified Docker Image with All Features${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓ Docker is available${NC}"
docker --version

# Check if we're in the right directory
if [ ! -f "app.py" ] || [ ! -f "worksheet_generator.py" ]; then
    echo -e "${RED}Error: Not in the correct directory${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

echo -e "${GREEN}✓ Project files found${NC}"

# Show build configuration
echo ""
echo -e "${BLUE}Build Configuration:${NC}"
echo "  Image name: ${IMAGE_NAME}:${VERSION}"
echo "  Build date: ${BUILD_DATE}"
echo "  VCS ref: ${VCS_REF}"
echo "  Dockerfile: Dockerfile (unified)"
echo ""

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p logs temp uploads downloads
echo -e "${GREEN}✓ Directories created${NC}"

# Build the Docker image
echo ""
echo -e "${YELLOW}Building Docker image...${NC}"
echo "This may take several minutes as it installs LibreOffice and fonts..."
echo ""

docker build \
    --build-arg BUILD_VERSION="${VERSION}" \
    --build-arg BUILD_DATE="${BUILD_DATE}" \
    --build-arg VCS_REF="${VCS_REF}" \
    -t "${IMAGE_NAME}:${VERSION}" \
    -t "${IMAGE_NAME}:latest" \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Docker image built successfully!${NC}"
    echo ""
    
    # Show image details
    echo -e "${BLUE}Image details:${NC}"
    docker images "${IMAGE_NAME}" | head -2
    echo ""
    
    # Test the image
    echo -e "${YELLOW}Testing the image...${NC}"
    
    # Test basic functionality
    echo "Testing basic container startup..."
    CONTAINER_ID=$(docker run -d -p 8082:8081 "${IMAGE_NAME}:${VERSION}")
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Container started successfully${NC}"
        
        # Wait for startup
        echo "Waiting for application to start..."
        sleep 10
        
        # Test health endpoint
        if curl -f http://localhost:8082/docs >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Application is responding${NC}"
        else
            echo -e "${YELLOW}⚠ Application might still be starting${NC}"
        fi
        
        # Test PDF conversion status
        if curl -f http://localhost:8082/pdf-status/ >/dev/null 2>&1; then
            echo -e "${GREEN}✓ PDF status endpoint is working${NC}"
        else
            echo -e "${YELLOW}⚠ PDF status endpoint not ready${NC}"
        fi
        
        # Cleanup test container
        docker stop "${CONTAINER_ID}" >/dev/null
        docker rm "${CONTAINER_ID}" >/dev/null
        echo -e "${GREEN}✓ Test container cleaned up${NC}"
    else
        echo -e "${RED}✗ Failed to start test container${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}🎉 Build completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo ""
    echo -e "${YELLOW}1. Run with Docker:${NC}"
    echo "   docker run -p 8081:8081 ${IMAGE_NAME}:${VERSION}"
    echo ""
    echo -e "${YELLOW}2. Run with docker-compose:${NC}"
    echo "   docker-compose up -d"
    echo ""
    echo -e "${YELLOW}3. Test PDF conversion:${NC}"
    echo "   docker run --rm ${IMAGE_NAME}:${VERSION} python test_pdf_conversion.py"
    echo ""
    echo -e "${YELLOW}4. Access the application:${NC}"
    echo "   API Documentation: http://localhost:8081/docs"
    echo "   PDF Status Check:  http://localhost:8081/pdf-status/"
    echo ""
    echo -e "${YELLOW}5. Monitor logs:${NC}"
    echo "   docker logs -f qa_worksheet_generator"
    echo ""
    
else
    echo ""
    echo -e "${RED}✗ Docker build failed!${NC}"
    echo ""
    echo -e "${YELLOW}Common solutions:${NC}"
    echo "1. Check your internet connection"
    echo "2. Make sure you have enough disk space (at least 2GB free)"
    echo "3. Try building without cache:"
    echo "   docker build --no-cache -t ${IMAGE_NAME}:${VERSION} ."
    echo "4. Check Docker daemon is running"
    echo "5. Try with more memory allocated to Docker"
    echo ""
    echo -e "${YELLOW}If the build continues to fail, you can try the minimal version:${NC}"
    echo "   docker build -f Dockerfile.minimal -t ${IMAGE_NAME}:minimal ."
    echo ""
    exit 1
fi
