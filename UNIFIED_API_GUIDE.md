# Unified API Structure v2.0

This document describes the new organized API structure with grouped endpoints and unified document creation.

## Folder Structure

When using the unified endpoint, documents are organized as follows:

```
all_data/
├── document_uuid_1/
│   ├── mindmap.png
│   ├── worksheet.pdf  
│   └── question_bank.pdf
├── document_uuid_2/
│   ├── mindmap.png
│   ├── worksheet.pdf
│   └── question_bank.pdf
```

## API Groups

### 1. Worksheet and Questions (`/api/v2/worksheets/`, `/api/v2/questions/`)

Generate worksheets and question banks from documents.

**Endpoints:**
- `GET /api/v2/worksheets/generate` - Generate worksheet
- `GET /api/v2/questions/generate` - Generate question bank

**Parameters:**
- `document_uuid` (required) - Document UUID from AI database
- `multiple_choice_count` - Number of multiple choice questions (-1=all, 0=none, N=exact)
- `true_false_count` - Number of true/false questions
- `short_answer_count` - Number of short answer questions
- `complete_count` - Number of fill-in-blank questions
- `generate_pdf` - Generate PDF files (default: true)
- `html_parsing` - Keep HTML markup (default: false)

### 2. Mindmaps (`/api/v2/mindmaps/`)

Generate and manage mindmap images.

**Endpoints:**
- `GET /api/v2/mindmaps/generate` - Generate mindmap from database
- `POST /api/v2/mindmaps/generate-from-json` - Generate from custom JSON
- `GET /api/v2/mindmaps/search` - Search mindmap documents
- `GET /api/v2/mindmaps/{document_uuid}` - Get mindmap details

**Parameters:**
- `document_uuid` (required) - Document UUID
- `width` - Image width in pixels (default: 1200)
- `height` - Image height in pixels (default: 800)

### 3. Status and Health (`/api/v2/status/`)

System status and health monitoring.

**Endpoints:**
- `GET /api/v2/status/health` - Complete system health check
- `GET /api/v2/status/pdf` - PDF conversion tools status
- `GET /api/v2/status/s3` - S3 storage service status

### 4. Documents and Lessons (`/api/v2/documents/`, `/api/v2/lessons/`)

Search and manage documents and lessons.

**Endpoints:**
- `GET /api/v2/documents/search` - Search documents by UUID/filename
- `GET /api/v2/documents/{document_uuid}` - Get document details
- `GET /api/v2/lessons/search` - Search lessons (legacy support)
- `GET /api/v2/lessons/{lesson_identifier}` - Get lesson details

## Unified Endpoint

### `POST /api/v2/create-all`

Creates mindmap, worksheet, and question bank for a document in one request.

**Key Features:**
- Creates organized folder structure: `all_data/{document_uuid}/`
- Standard filenames: `mindmap.png`, `worksheet.pdf`, `question_bank.pdf`
- Override protection: Returns existing files unless `override=true`
- Partial success handling: Reports which files were created vs failed

**Parameters:**
```json
{
  "document_uuid": "required-uuid-string",
  "override": false,
  "mindmap_width": 1200,
  "mindmap_height": 800,
  "multiple_choice_count": -1,
  "true_false_count": -1,
  "short_answer_count": -1,
  "complete_count": -1,
  "generate_pdf": true,
  "html_parsing": false
}
```

**Response Example:**
```json
{
  "api_version": "2.0",
  "endpoint": "create-all",
  "success": true,
  "data": {
    "document_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "folder_path": "all_data/123e4567-e89b-12d3-a456-426614174000",
    "status": "success",
    "created_files": {
      "mindmap": {
        "type": "mindmap",
        "format": "png",
        "s3_key": "all_data/123e4567-e89b-12d3-a456-426614174000/mindmap.png",
        "public_url": "https://pub-xxx.r2.dev/all_data/123e4567-e89b-12d3-a456-426614174000/mindmap.png",
        "standard_name": "mindmap"
      },
      "worksheet": {
        "type": "worksheet",
        "format": "pdf",
        "s3_key": "all_data/123e4567-e89b-12d3-a456-426614174000/worksheet.pdf",
        "public_url": "https://pub-xxx.r2.dev/all_data/123e4567-e89b-12d3-a456-426614174000/worksheet.pdf",
        "standard_name": "worksheet"
      },
      "question_bank": {
        "type": "question_bank",
        "format": "pdf", 
        "s3_key": "all_data/123e4567-e89b-12d3-a456-426614174000/question_bank.pdf",
        "public_url": "https://pub-xxx.r2.dev/all_data/123e4567-e89b-12d3-a456-426614174000/question_bank.pdf",
        "standard_name": "question_bank"
      }
    },
    "errors": {},
    "summary": {
      "total_requested": 3,
      "successfully_created": 3,
      "failed": 0,
      "success_rate": "3/3"
    },
    "created_at": "2025-09-07T10:30:00"
  }
}
```

## Error Handling

If documents already exist and `override=false`:

```json
{
  "api_version": "2.0",
  "endpoint": "create-all",
  "success": true,
  "data": {
    "document_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "folder_path": "all_data/123e4567-e89b-12d3-a456-426614174000",
    "exists": true,
    "override_required": true,
    "existing_files": {
      "mindmap": "https://pub-xxx.r2.dev/all_data/.../mindmap.png",
      "worksheet": "https://pub-xxx.r2.dev/all_data/.../worksheet.pdf",
      "question_bank": "https://pub-xxx.r2.dev/all_data/.../question_bank.pdf"
    },
    "message": "Documents already exist. Use override=true to regenerate."
  }
}
```

## Testing

Use the provided test script:

```bash
python test_unified_api.py
```

This will test all major endpoints and demonstrate the API functionality.

## Migration from v1

The v1 endpoints are still available for backward compatibility, but new integrations should use the v2 structure for better organization and features.

## File Management

All files are stored in Cloudflare R2 with public URLs. The folder structure ensures easy organization and prevents naming conflicts between different documents.
