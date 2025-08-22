#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the application
echo "Starting QA Worksheet Generator..."
docker-compose up -d --build

if [ $? -eq 0 ]; then
    echo "✅ Container started successfully!"
    echo "🌐 Application should be available at:"
    echo "   http://localhost:8081"
    echo "   http://localhost:8081/docs (API documentation)"
else
    echo "❌ Failed to start container!"
    echo "💡 Try using the simple compose file:"
    echo "   docker-compose -f docker-compose.simple.yml up -d --build"
fi
