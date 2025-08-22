#!/bin/bash

# Run script for QA Worksheet Generator Docker container

echo "Starting QA Worksheet Generator..."

# Check if .env file exists, if not copy from .env.example
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env file from .env.example..."
        cp .env.example .env
        echo "⚠️  Please review and update .env file with your configuration!"
    else
        echo "⚠️  No .env file found. Creating a basic one..."
        cat > .env << EOF
MONGO_URI=mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=ien
DB_NAME=ien
HOST=0.0.0.0
PORT=8081
EOF
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start with Docker Compose
if [ -f docker-compose.yml ]; then
    echo "🐳 Starting with Docker Compose..."
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo "✅ Container started successfully!"
        echo "🌐 Application should be available at:"
        echo "   http://localhost:8081"
        echo "   http://localhost:8081/docs (API documentation)"
        echo ""
        echo "📊 To check container status:"
        echo "   docker-compose ps"
        echo ""
        echo "📝 To view logs:"
        echo "   docker-compose logs -f"
        echo ""
        echo "🛑 To stop:"
        echo "   docker-compose down"
    else
        echo "❌ Failed to start container!"
        exit 1
    fi
else
    # Fallback to direct docker run
    echo "🚀 Starting with docker run..."
    docker run -d \
        --name qa_worksheet_generator \
        -p 8081:8081 \
        --env-file .env \
        -v "$(pwd)/logs:/app/logs" \
        qa-worksheet-generator:latest
    
    if [ $? -eq 0 ]; then
        echo "✅ Container started successfully!"
        echo "🌐 Application should be available at http://localhost:8081"
    else
        echo "❌ Failed to start container!"
        exit 1
    fi
fi
