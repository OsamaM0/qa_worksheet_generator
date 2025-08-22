@echo off
REM Build script for QA Worksheet Generator Docker image (Windows)

echo Building QA Worksheet Generator Docker image...

REM Build the Docker image
docker build -t qa-worksheet-generator:latest .

if %ERRORLEVEL% EQU 0 (
    echo ✅ Docker image built successfully!
    echo 📋 Available images:
    docker images | findstr qa-worksheet-generator
    echo.
    echo 🚀 To run the container:
    echo    docker run -p 8081:8081 qa-worksheet-generator:latest
    echo.
    echo 🐳 Or use Docker Compose:
    echo    docker-compose up -d
) else (
    echo ❌ Docker build failed!
    exit /b 1
)
