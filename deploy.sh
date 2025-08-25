#!/bin/bash
# ==============================================================================
# ONE-CLICK DEPLOYMENT SCRIPT
# Saudi Edu Worksheet Generator - Complete Setup
# ==============================================================================
# This script automates the entire deployment process including:
# - Building the unified Docker image
# - Setting up the environment
# - Running health checks
# - Starting the application
# ==============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Saudi Edu Worksheet Generator"
IMAGE_NAME="worksheet-generator"
CONTAINER_NAME="qa_worksheet_generator"
APP_PORT="8081"
TEST_PORT="8082"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                              ║${NC}"
echo -e "${BLUE}║           ${CYAN}${APP_NAME}${BLUE}            ║${NC}"
echo -e "${BLUE}║                    One-Click Deployment                      ║${NC}"
echo -e "${BLUE}║                                                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print step headers
print_step() {
    echo -e "${CYAN}[STEP $1]${NC} $2"
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local max_attempts=30
    local attempt=1
    
    echo "Waiting for service to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if curl -f "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Service is ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    echo -e "${RED}✗ Service failed to start within $((max_attempts * 2)) seconds${NC}"
    return 1
}

# Step 1: Prerequisites Check
print_step "1" "Checking Prerequisites"

# Check Docker
if command_exists docker; then
    echo -e "${GREEN}✓ Docker is installed${NC}"
    docker --version
else
    echo -e "${RED}✗ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if command_exists docker-compose; then
    echo -e "${GREEN}✓ Docker Compose is installed${NC}"
    docker-compose --version
else
    echo -e "${YELLOW}⚠ Docker Compose not found, will use docker run instead${NC}"
fi

# Check if Docker daemon is running
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker daemon is running${NC}"
else
    echo -e "${RED}✗ Docker daemon is not running${NC}"
    echo "Please start Docker daemon and try again"
    exit 1
fi

# Check project files
if [ ! -f "app.py" ] || [ ! -f "worksheet_generator.py" ]; then
    echo -e "${RED}✗ Project files not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Step 2: Environment Setup
print_step "2" "Setting Up Environment"

# Create necessary directories
echo "Creating directories..."
mkdir -p logs temp uploads downloads
echo -e "${GREEN}✓ Directories created${NC}"

# Check for .env file
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Found .env file${NC}"
else
    echo -e "${YELLOW}⚠ No .env file found, using defaults${NC}"
    echo "Consider creating a .env file with your MongoDB connection details"
fi

echo ""

# Step 3: Clean up existing containers
print_step "3" "Cleaning Up Previous Deployments"

# Stop and remove existing container
if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    echo "Stopping existing container..."
    docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    echo "Removing existing container..."
    docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    echo -e "${GREEN}✓ Previous deployment cleaned up${NC}"
else
    echo -e "${GREEN}✓ No previous deployment found${NC}"
fi

echo ""

# Step 4: Build Docker Image
print_step "4" "Building Docker Image"

echo "Building unified Docker image with all features..."
echo "This may take several minutes..."
echo ""

# Build with progress output
docker build \
    --build-arg BUILD_VERSION="latest" \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VCS_REF="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
    -t "${IMAGE_NAME}:latest" \
    .

echo -e "${GREEN}✓ Docker image built successfully${NC}"
echo ""

# Step 5: Test Build
print_step "5" "Testing Docker Image"

echo "Starting test container..."
TEST_CONTAINER_ID=$(docker run -d -p "${TEST_PORT}:8081" "${IMAGE_NAME}:latest")

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test container started${NC}"
    
    # Wait for service to be ready
    if wait_for_service "http://localhost:${TEST_PORT}/docs"; then
        echo -e "${GREEN}✓ Application is responding${NC}"
        
        # Test PDF conversion status
        echo "Testing PDF conversion capabilities..."
        if curl -f "http://localhost:${TEST_PORT}/pdf-status/" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ PDF conversion endpoint is working${NC}"
            
            # Get PDF status details
            PDF_STATUS=$(curl -s "http://localhost:${TEST_PORT}/pdf-status/" | grep -o '"pdf_conversion_available":[^,]*' | cut -d':' -f2)
            if [ "$PDF_STATUS" = "true" ]; then
                echo -e "${GREEN}✓ PDF conversion is fully operational${NC}"
            else
                echo -e "${YELLOW}⚠ PDF conversion may have issues${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ PDF status endpoint not responding${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Application may not be fully ready${NC}"
    fi
    
    # Clean up test container
    echo "Cleaning up test container..."
    docker stop "${TEST_CONTAINER_ID}" >/dev/null
    docker rm "${TEST_CONTAINER_ID}" >/dev/null
    echo -e "${GREEN}✓ Test container cleaned up${NC}"
else
    echo -e "${RED}✗ Failed to start test container${NC}"
    exit 1
fi

echo ""

# Step 6: Deploy Application
print_step "6" "Deploying Application"

# Choose deployment method
if command_exists docker-compose && [ -f "docker-compose.yml" ]; then
    echo "Using Docker Compose for deployment..."
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Application deployed with Docker Compose${NC}"
    else
        echo -e "${RED}✗ Docker Compose deployment failed${NC}"
        echo "Falling back to direct Docker run..."
        
        # Fallback to docker run
        docker run -d \
            --name "${CONTAINER_NAME}" \
            -p "${APP_PORT}:8081" \
            --restart unless-stopped \
            "${IMAGE_NAME}:latest"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Application deployed with Docker run${NC}"
        else
            echo -e "${RED}✗ Deployment failed${NC}"
            exit 1
        fi
    fi
else
    echo "Using direct Docker run for deployment..."
    docker run -d \
        --name "${CONTAINER_NAME}" \
        -p "${APP_PORT}:8081" \
        --restart unless-stopped \
        -v "$(pwd)/logs:/app/logs" \
        -v "$(pwd)/temp:/app/temp" \
        "${IMAGE_NAME}:latest"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Application deployed with Docker run${NC}"
    else
        echo -e "${RED}✗ Deployment failed${NC}"
        exit 1
    fi
fi

echo ""

# Step 7: Health Check
print_step "7" "Final Health Check"

echo "Waiting for application to be fully ready..."
if wait_for_service "http://localhost:${APP_PORT}/docs"; then
    echo -e "${GREEN}✓ Application is running and healthy${NC}"
    
    # Final PDF conversion check
    echo "Performing final PDF conversion check..."
    PDF_RESPONSE=$(curl -s "http://localhost:${APP_PORT}/pdf-status/")
    if echo "$PDF_RESPONSE" | grep -q '"pdf_conversion_available":true'; then
        echo -e "${GREEN}✓ PDF conversion is fully operational${NC}"
    else
        echo -e "${YELLOW}⚠ PDF conversion may need attention${NC}"
        echo "Check logs: docker logs ${CONTAINER_NAME}"
    fi
else
    echo -e "${RED}✗ Application failed final health check${NC}"
    echo "Check logs: docker logs ${CONTAINER_NAME}"
    exit 1
fi

echo ""

# Step 8: Summary
print_step "8" "Deployment Summary"

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}Application Details:${NC}"
echo "  • Container Name: ${CONTAINER_NAME}"
echo "  • Image: ${IMAGE_NAME}:latest"
echo "  • Port: ${APP_PORT}"
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo "  • API Documentation: ${CYAN}http://localhost:${APP_PORT}/docs${NC}"
echo "  • PDF Status Check:  ${CYAN}http://localhost:${APP_PORT}/pdf-status/${NC}"
echo "  • Search Lessons:    ${CYAN}http://localhost:${APP_PORT}/search-lessons/?query=test${NC}"
echo ""
echo -e "${BLUE}Management Commands:${NC}"
echo "  • View logs:     ${YELLOW}docker logs -f ${CONTAINER_NAME}${NC}"
echo "  • Stop app:      ${YELLOW}docker stop ${CONTAINER_NAME}${NC}"
echo "  • Start app:     ${YELLOW}docker start ${CONTAINER_NAME}${NC}"
echo "  • Restart app:   ${YELLOW}docker restart ${CONTAINER_NAME}${NC}"
echo "  • Remove app:    ${YELLOW}docker rm -f ${CONTAINER_NAME}${NC}"
echo ""
echo -e "${BLUE}Testing Commands:${NC}"
echo "  • Test PDF:      ${YELLOW}docker exec -it ${CONTAINER_NAME} python test_pdf_conversion.py${NC}"
echo "  • Shell access:  ${YELLOW}docker exec -it ${CONTAINER_NAME} /bin/bash${NC}"
echo ""

# Show container status
echo -e "${BLUE}Current Status:${NC}"
docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Final reminder
echo -e "${CYAN}💡 Tip:${NC} Bookmark ${CYAN}http://localhost:${APP_PORT}/docs${NC} for easy API access"
echo -e "${CYAN}📖 Help:${NC} Check DEPLOYMENT_GUIDE.md for advanced configuration"
echo -e "${CYAN}🔧 Debug:${NC} If PDF conversion issues occur, run the diagnostic script"
echo ""
echo -e "${GREEN}Happy worksheet generating! 📝✨${NC}"
