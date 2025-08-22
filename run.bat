@echo off
REM Run script for QA Worksheet Generator Docker container (Windows)

echo Starting QA Worksheet Generator...

REM Check if .env file exists, if not copy from .env.example
if not exist .env (
    if exist .env.example (
        echo 📝 Creating .env file from .env.example...
        copy .env.example .env
        echo ⚠️  Please review and update .env file with your configuration!
    ) else (
        echo ⚠️  No .env file found. Creating a basic one...
        (
            echo MONGO_URI=mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=ien
            echo DB_NAME=ien
            echo HOST=0.0.0.0
            echo PORT=8081
        ) > .env
    )
)

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Start with Docker Compose
if exist docker-compose.yml (
    echo 🐳 Starting with Docker Compose...
    echo 💡 If build fails, try: docker-compose -f docker-compose.yml build --build-arg DOCKERFILE=Dockerfile.minimal
    docker-compose up -d
    
    if %ERRORLEVEL% EQU 0 (
        echo ✅ Container started successfully!
        echo 🌐 Application should be available at:
        echo    http://localhost:8081
        echo    http://localhost:8081/docs ^(API documentation^)
        echo.
        echo 📊 To check container status:
        echo    docker-compose ps
        echo.
        echo 📝 To view logs:
        echo    docker-compose logs -f
        echo.
        echo 🛑 To stop:
        echo    docker-compose down
    ) else (
        echo ❌ Failed to start container!
        exit /b 1
    )
) else (
    REM Fallback to direct docker run
    echo 🚀 Starting with docker run...
    docker run -d --name qa_worksheet_generator -p 8081:8081 --env-file .env -v "%cd%\logs:/app/logs" qa-worksheet-generator:latest
    
    if %ERRORLEVEL% EQU 0 (
        echo ✅ Container started successfully!
        echo 🌐 Application should be available at http://localhost:8081
    ) else (
        echo ❌ Failed to start container!
        exit /b 1
    )
)
