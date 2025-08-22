# 🚀 Secure Multi-Stage Docker Deployment

This Docker setup uses multi-stage builds to create a secure production image with **no source code** included in the final container.

## 🔒 Security Features

### Multi-Stage Build Protection
- **Build Stage**: Contains source code, build tools, and compiles the application
- **Production Stage**: Contains only compiled wheel packages and runtime dependencies
- **No Source Code**: Your Python source code never exists in the final image
- **Minimal Attack Surface**: Only essential runtime components included

### Runtime Security
- **Non-root User**: Application runs as `appuser` with limited privileges
- **Read-only Filesystem**: Container filesystem is read-only for security
- **No New Privileges**: Prevents privilege escalation
- **Temporary Filesystems**: Uses tmpfs for temporary data

## 📦 Build Process

### What Happens During Build
1. **Source Code → Wheel Package**: Python source is compiled into `.whl` format
2. **Dependencies Installation**: All dependencies installed in isolated environment
3. **Asset Copying**: Only necessary files (logo, configs) copied to production
4. **Source Removal**: Original source code discarded after compilation

### Build the Secure Image
```bash
# Build the multi-stage image
docker build -t worksheet-api:secure .

# Build with specific tag
docker build -t worksheet-api:v1.0.0 .
```

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f worksheet-generator

# Stop services
docker-compose down
```

### Option 2: Direct Docker Run
```bash
# Run with environment variables
docker run -d \
  --name worksheet-api \
  -p 8000:8000 \
  -e MONGO_URI="your_mongo_connection" \
  -e MONGO_DB_NAME="ien" \
  -e ENABLE_PDF_GENERATION="true" \
  -v $(pwd)/logo.png:/app/logo.png:ro \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  worksheet-api:secure
```

## ⚙️ Environment Configuration

### Required Environment Variables
```bash
# MongoDB Configuration
MONGO_URI=mongodb://user:pass@host:port/database
MONGO_DB_NAME=ien

# Optional Configuration
ENABLE_PDF_GENERATION=true  # Enable/disable PDF conversion
HOST=0.0.0.0               # API host
PORT=8000                  # API port
```

### Environment File (.env)
Create a `.env` file in your project root:
```env
MONGO_URI=mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=ien
MONGO_DB_NAME=ien
ENABLE_PDF_GENERATION=true
```

## 🔍 Verification

### Check Security
```bash
# Verify no source code in container
docker run --rm worksheet-api:secure find /app -name "*.py" | grep -v start_app.py

# Should only show start_app.py (minimal launcher)

# Verify running as non-root
docker run --rm worksheet-api:secure whoami
# Should output: appuser
```

### Test API
```bash
# Health check
curl http://localhost:8000/docs

# Test worksheet generation
curl "http://localhost:8000/generate-worksheet/?lesson_id=600&output=worksheet&num_questions=3&enable_pdf=true"
```

## 📊 Image Comparison

| Feature | Regular Build | Multi-Stage Build |
|---------|---------------|-------------------|
| Source Code | ✅ Included | ❌ **Not Included** |
| Image Size | Larger | **Smaller** |
| Build Tools | Included | **Removed** |
| Security | Basic | **Enhanced** |
| Attack Surface | Large | **Minimal** |

## 🛠️ Development vs Production

### Development (with source access)
```bash
# Run with volume mount for development
docker run -d \
  -p 8000:8000 \
  -v $(pwd):/app \
  -e MONGO_URI="mongodb://localhost:27017/ien" \
  python:3.10-slim \
  bash -c "cd /app && pip install -r requirements.txt && python app.py"
```

### Production (secure, no source)
```bash
# Use the multi-stage built image
docker-compose up -d
```

## 🔒 What's Protected

### In Build Stage (Discarded)
- ✅ `app.py` - Main application source
- ✅ `worksheet_generator.py` - Core logic
- ✅ `.env` files - Environment secrets
- ✅ Development tools and dependencies
- ✅ Git history and metadata

### In Production Stage (Kept)
- ✅ Compiled wheel package (bytecode only)
- ✅ Runtime dependencies
- ✅ Logo and static assets
- ✅ Minimal startup script
- ✅ System libraries only

## 🚨 Important Notes

1. **No Source Recovery**: Once built, source code cannot be extracted from the production image
2. **Debugging**: For debugging, use development setup or check logs
3. **Updates**: Rebuild image for any source code changes
4. **Backup**: Keep your source code in version control
5. **Secrets**: Never include secrets in the image - use environment variables

## 🎯 Production Ready

This setup is production-ready with:
- ✅ Security hardening
- ✅ Health checks
- ✅ Graceful shutdowns  
- ✅ Resource limits
- ✅ Logging integration
- ✅ Arabic language support
- ✅ PDF generation with watermarks

Your source code remains completely protected! 🔐
