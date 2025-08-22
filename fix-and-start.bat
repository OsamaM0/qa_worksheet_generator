@echo off
REM Fix Docker Compose deployment issues

echo 🔧 Preparing Docker environment...

REM Create required directories
if not exist logs mkdir logs
echo ✅ Created logs directory

REM Ensure logo.png exists
if not exist logo.png (
    echo Creating placeholder logo.png...
    echo. 2>logo.png
    echo ✅ Created placeholder logo.png
) else (
    echo ✅ logo.png already exists
)

REM Stop any existing containers
echo 🛑 Stopping existing containers...
docker-compose down 2>nul

REM Clean up any problematic volumes
echo 🧹 Cleaning up Docker...
docker system prune -f 2>nul

REM Start with root configuration (avoids permission issues)
echo 🚀 Starting with root configuration (no permission issues)...
docker-compose up -d --build

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ SUCCESS! Container started successfully!
    echo 🌐 Application available at:
    echo    http://localhost:8081
    echo    http://localhost:8081/docs
    echo.
    echo 📊 Check status: docker-compose ps
    echo 📝 View logs: docker-compose logs -f
    echo 🛑 To stop: docker-compose down
) else (
    echo.
    echo ❌ Build failed. Trying alternative configuration...
    docker-compose -f docker-compose.simple.yml up -d --build
    
    if %ERRORLEVEL% EQU 0 (
        echo ✅ SUCCESS with simple configuration!
        echo 🌐 Application available at http://localhost:8081
    ) else (
        echo ❌ All configurations failed.
        echo 💡 Check the troubleshooting guide: DOCKER_TROUBLESHOOTING.md
    )
)
