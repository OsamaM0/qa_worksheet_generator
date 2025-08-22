#!/bin/bash

# Build script for QA Worksheet Generator Docker image

echo "Building QA Worksheet Generator Docker image..."

# Build the Docker image
docker build -t qa-worksheet-generator:latest .

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo "📋 Available images:"
    docker images | grep qa-worksheet-generator
    echo ""
    echo "🚀 To run the container:"
    echo "   docker run -p 8081:8081 qa-worksheet-generator:latest"
    echo ""
    echo "🐳 Or use Docker Compose:"
    echo "   docker-compose up -d"
else
    echo "❌ Docker build failed!"
    exit 1
fi
