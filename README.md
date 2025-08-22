# Saudi Edu Worksheet Generator

A FastAPI-based web service for generating Arabic educational worksheets and question banks with PDF conversion capabilities.

## Features

- 🇸🇦 **Arabic Language Support**: Full RTL text rendering and Arabic font support
- 📄 **Multiple Formats**: Generate JSON, DOCX, and PDF files
- 🎯 **Flexible Output**: Support for worksheets and question banks
- 🔄 **DOCX to PDF Conversion**: Maintains original formatting with logo watermarks
- 📊 **Question Management**: Support for multiple choice and essay questions
- 🔧 **Configurable**: Environment-based configuration
- 🐳 **Docker Ready**: Full containerization support

## Quick Start

### Local Development

1. **Clone and setup**:
```bash
git clone <repository-url>
cd qa_worksheet_generator
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your MongoDB credentials
```

3. **Run the application**:
```bash
python app.py
```

4. **Access the API**:
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/docs

### Docker Deployment

1. **Build and run with Docker**:
```bash
docker build -t worksheet-generator .
docker run -p 8000:8000 --env-file .env worksheet-generator
```

2. **Or use Docker Compose**:
```bash
docker-compose up -d
```

## API Usage

### Generate Worksheet/Question Bank

```http
GET /generate-worksheet/?lesson_id=600&output=worksheet&num_questions=5&generate_pdf=true
```

**Parameters**:
- `lesson_id` (required): Lesson ID from database
- `output`: "worksheet" or "question_bank" (default: "worksheet")
- `num_questions`: Number of questions to include (0 = all)
- `generate_pdf`: Generate PDF files (default: true)
- `html_parsing`: Keep HTML markup (default: false)
- `mongo_uri`: Override MongoDB URI (optional)
- `db_name`: Override database name (optional)

**Response**:
```json
{
  "lesson_title": "درس الرياضيات",
  "base_filename": "درس_الرياضيات_ورقة_عمل",
  "generate_pdf": true,
  "files": {
    "json_no_solutions": "/tmp/file_no_solutions.json",
    "json_with_solutions": "/tmp/file_with_solutions.json",
    "docx_no_solutions": "/tmp/file_no_solutions.docx",
    "docx_with_solutions": "/tmp/file_with_solutions.docx",
    "pdf_no_solutions": "/tmp/file_no_solutions.pdf",
    "pdf_with_solutions": "/tmp/file_with_solutions.pdf"
  }
}
```

## Environment Configuration

Create a `.env` file with the following variables:

```env
# MongoDB Configuration
MONGO_URI=mongodb://username:password@host:port/database?authSource=database
DB_NAME=your_database_name

# Application Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=False

# Optional
LOGO_PATH=logo.png
```

## File Structure

```
qa_worksheet_generator/
├── app.py                 # Main FastAPI application
├── worksheet_generator.py # Core worksheet generation logic
├── logo.png              # Logo for PDF watermarks
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose setup
├── .env                  # Environment variables
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## PDF Conversion Methods

The application uses multiple fallback methods for DOCX to PDF conversion:

1. **docx2pdf** (Primary): Fast Windows-optimized conversion
2. **comtypes**: Direct Microsoft Word automation
3. **LibreOffice**: Cross-platform command-line conversion
4. **Graceful degradation**: Returns DOCX if PDF conversion fails

## Arabic Text Support

- **RTL Text Flow**: Proper right-to-left text rendering
- **Arabic Fonts**: Supports Arabic font families
- **Mixed Content**: Handles Arabic-English mixed text
- **Cultural Formatting**: Arabic numbering and bullet styles

## Logo Watermarking

- **Transparent Background**: 10% opacity logo watermark
- **Auto-scaling**: Logo scales to 50% of page size
- **Centered Placement**: Logo positioned in page center
- **ReportLab Integration**: Uses ReportLab for watermark creation

## Docker Configuration

### Single Container
```bash
docker run -d \
  --name worksheet-generator \
  -p 8000:8000 \
  -e MONGO_URI="your_mongo_uri" \
  -e DB_NAME="your_db_name" \
  -v $(pwd)/logo.png:/app/logo.png:ro \
  worksheet-generator
```

### Docker Compose
```yaml
services:
  worksheet-generator:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MONGO_URI=your_mongo_uri
      - DB_NAME=your_db_name
    volumes:
      - ./logo.png:/app/logo.png:ro
```

## Health Monitoring

The application includes built-in health checks:
- **Endpoint**: `/docs` (FastAPI automatic documentation)
- **Docker Health Check**: Automatic container health monitoring
- **Startup Time**: ~5 seconds average startup time

## Development

### Testing
```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### API Documentation
Visit `http://localhost:8000/docs` for interactive API documentation.

## Troubleshooting

### Common Issues

1. **PDF Conversion Fails**: Ensure docx2pdf or LibreOffice is installed
2. **Arabic Text Issues**: Verify Arabic fonts are available in the system
3. **MongoDB Connection**: Check network connectivity and credentials
4. **Docker Build Issues**: Ensure Docker has sufficient memory allocated

### Logs
```bash
# Docker logs
docker logs worksheet-generator

# Docker Compose logs
docker-compose logs -f
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions, please create an issue in the repository or contact the development team.
