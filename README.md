# QA Worksheet Generator

A FastAPI-based application for generating educational worksheets and question banks from the AI database.

## Overview

This application generates Arabic educational worksheets and question banks in multiple formats (JSON, DOCX, PDF) from a MongoDB database containing questions and worksheet metadata.

## Database Structure

### AI Database (Current)
- **Database**: `ai`
- **Collections**: `questions`, `worksheets`
- **Approach**: Document UUID-based with simplified relationships

### Key Features
- Generate worksheets and question banks
- Support for 4 question types: multiple choice, true/false, short answer, complete
- Export to JSON, DOCX, and PDF formats
- S3/Cloudflare R2 integration for file storage
- Arabic language support with proper RTL formatting

## Quick Start

### Using Docker (Recommended)

1. Clone the repository
2. Copy `.env.example` to `.env` and configure your settings
3. Run with Docker Compose:

```bash
docker-compose up -d
```

The application will be available at `http://localhost:8081`

## API Endpoints

### Main Endpoints

#### Generate Worksheet (AI Database)
```
GET /generate-worksheet/?document_uuid={uuid}
```
- **document_uuid**: Document UUID from AI database
- **output**: "worksheet" or "question_bank" (default: "worksheet")
- **generate_pdf**: Generate PDF files (default: true)

#### Search Documents
```
GET /search-documents/?query={search_term}
```
Search for documents by UUID, filename, or text fragment.

#### Document Details
```
GET /document-details/{document_uuid}
```
Get detailed information about a document including both worksheet and questions data.

### Legacy Endpoints

#### Generate Worksheet (Legacy)
```
GET /generate-worksheet-legacy/?lesson_id={id}
```
Maintains backward compatibility with the old IEN database structure.

## Configuration

### Environment Variables

```bash
# MongoDB Configuration
MONGO_URI=mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ai?authSource=ai
DB_NAME=ai

# Application Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=True

# S3 Configuration (Optional)
S3_API_TOKEN=your_api_token
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_ACCOUNT_ID=your_account_id
S3_ENDPOINT=https://your_account_id.r2.cloudflarestorage.com
S3_BUCKET_NAME=your_bucket_name
```

## Data Structure

### Questions Collection
```json
{
  "document_uuid": "7bf16cad-019a-4328-ab4a-bb0a35505ff9",
  "filename": "النثر السعودي 2- فن المقالة",
  "questions": {
    "multiple_choice": [...],
    "true_false": [...],
    "short_answer": [...],
    "complete": [...]
  }
}
```

### Worksheets Collection
```json
{
  "document_uuid": "7bf16cad-019a-4328-ab4a-bb0a35505ff9",
  "filename": "النثر السعودي 2- فن المقالة",
  "worksheet": {
    "goals": [...],
    "applications": [...],
    "vocabulary": [...],
    "teacher_guidelines": [...]
  }
}
```

## Example Usage

### Search for Documents
```bash
curl "http://localhost:8000/search-documents/?query=النثر السعودي"
```

### Generate Worksheet
```bash
curl "http://localhost:8000/generate-worksheet/?document_uuid=7bf16cad-019a-4328-ab4a-bb0a35505ff9&output=worksheet"
```

### Generate Question Bank
```bash
curl "http://localhost:8000/generate-worksheet/?document_uuid=7bf16cad-019a-4328-ab4a-bb0a35505ff9&output=question_bank"
```

## Output Formats

- **JSON**: Structured data with all questions and metadata
- **DOCX**: Formatted Word document with Arabic support
- **PDF**: Generated from DOCX with proper Arabic rendering (requires LibreOffice)

## Development

### Local Setup

1. Install Python 3.8+
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables
4. Run the application:
```bash
python app.py
```

### Docker Development

```bash
docker-compose -f docker-compose.yml up -d
```

## Migration from IEN Database

If you're migrating from the old IEN database structure, see [AI_DATABASE_MIGRATION_GUIDE.md](AI_DATABASE_MIGRATION_GUIDE.md) for detailed migration instructions.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.
