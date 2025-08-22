#!/bin/bash

# Fix Docker Compose deployment issues

echo "🔧 Preparing Docker environment..."

# Create required directories
mkdir -p logs
echo "✅ Created logs directory"

# Ensure logo.png exists
if [ ! -f logo.png ]; then
    echo "Creating placeholder logo.png..."
    touch logo.png
    echo "✅ Created placeholder logo.png"
else
    echo "✅ logo.png already exists"
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null

# Clean up any problematic volumes
echo "🧹 Cleaning up Docker..."
docker system prune -f 2>/dev/null

# Start with bulletproof configuration
echo "🚀 Starting with bulletproof configuration..."
docker-compose up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS! Container started successfully!"
    echo "🌐 Application available at:"
    echo "   http://localhost:8081"
    echo "   http://localhost:8081/docs"
    echo ""
    echo "📊 Check status: docker-compose ps"
    echo "📝 View logs: docker-compose logs -f"
    echo "🛑 To stop: docker-compose down"
else
    echo ""
    echo "❌ Build failed. Trying alternative configuration..."
    docker-compose -f docker-compose.simple.yml up -d --build
    
    if [ $? -eq 0 ]; then
        echo "✅ SUCCESS with simple configuration!"
        echo "🌐 Application available at http://localhost:8081"
    else
        echo "❌ All configurations failed."
        echo "💡 Check the troubleshooting guide: DOCKER_TROUBLESHOOTING.md"
    fi
fi
