# QA Worksheet Generator API v2.0

## Overview

The new API v2.0 provides a unified and organized structure for generating worksheets, questions, and mindmaps with improved file management and UUID-based document organization.

## API Structure

### Group 1: Worksheet and Questions
- **`/api/v2/worksheets/generate`** - Generate worksheets
- **`/api/v2/questions/generate`** - Generate question banks

### Group 2: Mindmaps
- **`/api/v2/mindmaps/generate`** - Generate mindmap images from database
- **`/api/v2/mindmaps/generate-from-json`** - Generate mindmap images from JSON data
- **`/api/v2/mindmaps/search`** - Search mindmap documents
- **`/api/v2/mindmaps/{document_uuid}`** - Get mindmap details

### Group 3: Status and Health
- **`/api/v2/status/pdf`** - Check PDF conversion status
- **`/api/v2/status/s3`** - Check S3 storage status
- **`/api/v2/status/health`** - Complete system health check

### Group 4: Lessons and Documents
- **`/api/v2/documents/search`** - Search documents
- **`/api/v2/documents/{document_uuid}`** - Get document details
- **`/api/v2/lessons/search`** - Search lessons (legacy support)
- **`/api/v2/lessons/{lesson_identifier}`** - Get lesson details (legacy support)

### Unified Endpoint
- **`/api/v2/create-all`** - Create mindmap, worksheet, and question bank in one call

### File Management
- **`/api/v2/files/list`** - List uploaded files
- **`/api/v2/files/download/{file_key:path}`** - Download files

### API Information
- **`/api/v2/info`** - Get API information and endpoints

## Key Features

### 1. UUID-Based Document Management
All documents are organized by UUID in folder structure:
```
uuid_documents/{document_uuid}/
├── Mindmap.png
├── Worksheet_with_solutions.json
├── Worksheet_with_solutions.docx
├── Worksheet_with_solutions.pdf
├── Worksheet_no_solutions.json
├── Worksheet_no_solutions.docx
├── Worksheet_no_solutions.pdf
├── Question_bank_with_solutions.json
├── Question_bank_with_solutions.docx
├── Question_bank_with_solutions.pdf
├── Question_bank_no_solutions.json
├── Question_bank_no_solutions.docx
└── Question_bank_no_solutions.pdf
```

### 2. Override Functionality
- If documents exist for a UUID, the API returns existing paths
- Use `override=true` parameter to regenerate documents
- Prevents accidental duplication

### 3. Unified Response Format
All v2 endpoints return consistent format:
```json
{
  "api_version": "2.0",
  "endpoint": "endpoint_name",
  "success": true,
  "data": { ... }
}
```

## Usage Examples

### Create All Documents
```bash
curl -X POST "http://localhost:8000/api/v2/create-all?document_uuid=12345678-1234-1234-1234-123456789abc"
```

### Generate Only Worksheet
```bash
curl "http://localhost:8000/api/v2/worksheets/generate?document_uuid=12345678-1234-1234-1234-123456789abc"
```

### Generate Mindmap
```bash
curl "http://localhost:8000/api/v2/mindmaps/generate?document_uuid=12345678-1234-1234-1234-123456789abc&width=1600&height=1000"
```

### Check System Health
```bash
curl "http://localhost:8000/api/v2/status/health"
```

### Search Documents
```bash
curl "http://localhost:8000/api/v2/documents/search?query=lesson1"
```

## Parameters

### Question Type Controls
- `multiple_choice_count`: Number of multiple choice questions (-1=all, 0=none, N=exact)
- `true_false_count`: Number of true/false questions (-1=all, 0=none, N=exact)
- `short_answer_count`: Number of short answer questions (-1=all, 0=none, N=exact)
- `complete_count`: Number of fill-in-blank questions (-1=all, 0=none, N=exact)

### File Generation
- `generate_pdf`: Generate PDF files (default: true)
- `html_parsing`: Keep HTML markup (default: false)

### Database
- `mongo_uri`: Override MongoDB URI
- `db_name`: Override database name

## Migration from v1

All original endpoints remain functional for backward compatibility:
- `/generate-worksheet/` → `/api/v2/worksheets/generate`
- `/generate-mindmap-image/` → `/api/v2/mindmaps/generate`
- `/search-documents/` → `/api/v2/documents/search`

## Error Handling

Errors are returned in consistent format:
```json
{
  "api_version": "2.0",
  "endpoint": "endpoint_name",
  "success": false,
  "error": "Error description"
}
```

## Authentication

Currently, the API does not require authentication. All endpoints are publicly accessible.

## Rate Limiting

No rate limiting is currently implemented. Consider implementing rate limiting for production use.

## Support

For issues or questions, refer to the API documentation at `/docs` or contact the development team.
