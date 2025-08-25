# QA Worksheet Generator - S3 Integration Update

## Overview

The QA Worksheet Generator has been updated to save generated files to Cloudflare R2 (S3-compatible) storage instead of temporary local directories. This provides better scalability, persistence, and accessibility of generated worksheets.

## What's Changed

### 1. New S3 Service (`s3_service.py`)
- Complete S3/R2 integration using boto3
- Automatic file upload with organized folder structure
- Public URL generation for direct file access
- Health checks and error handling

### 2. Updated API Response
The `/generate-worksheet/` endpoint now returns:
```json
{
  "lesson_title": "Lesson Title",
  "base_filename": "lesson_worksheet",
  "generate_pdf": true,
  "files": {
    "json_no_solutions": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/json_no_solutions.json",
    "json_with_solutions": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/json_with_solutions.json",
    "docx_no_solutions": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/docx_no_solutions.docx",
    "docx_with_solutions": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/docx_with_solutions.docx",
    "pdf_no_solutions": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/pdf_no_solutions.pdf",
    "pdf_with_solutions": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/pdf_with_solutions.pdf"
  },
  "s3_uploads": {
    "status": "success",
    "files": {
      "json_no_solutions": {
        "status": "success",
        "s3_key": "worksheets/20250825_123456_abc12345/json_no_solutions.json",
        "bucket": "worksheet",
        "public_url": "https://pub-dcdb150a91310324ecc43b417e14446b.r2.dev/worksheets/20250825_123456_abc12345/json_no_solutions.json",
        "file_size": 12345,
        "content_type": "application/json",
        "upload_time": "2025-08-25T12:34:56.789"
      }
    },
    "upload_time": "2025-08-25T12:34:56.789",
    "folder": "worksheets/20250825_123456_abc12345"
  }
}
```

### 3. New API Endpoints

#### Check S3 Status
```bash
GET /s3-status/
```
Returns the health and configuration status of S3 storage.

#### Download Files
```bash
GET /download/{file_key:path}
```
Download files from S3 storage (redirects to public URL).

#### List Uploaded Files
```bash
GET /list-files/?prefix=worksheets&limit=50
```
List files in S3 storage with optional filtering.

## Configuration

All S3 configuration is handled through environment variables in `.env`:

```env
# S3 Configuration
S3_API_TOKEN=your_api_token
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_ACCOUNT_ID=your_account_id
S3_ENDPOINT=https://dcdb150a91310324ecc43b417e14446b.r2.cloudflarestorage.com
S3_BUCKET_NAME=worksheet
```

## File Organization

Files are organized in S3 with the following structure:
```
worksheets/
├── Lesson_Title_1/
│   ├── 20250825_123456_abc12345/
│   │   ├── json_no_solutions.json
│   │   ├── json_with_solutions.json
│   │   ├── docx_no_solutions.docx
│   │   ├── docx_with_solutions.docx
│   │   ├── pdf_no_solutions.pdf
│   │   └── pdf_with_solutions.pdf
```

## Benefits

1. **Scalability**: No local storage limitations
2. **Persistence**: Files are permanently stored and accessible
3. **Direct Access**: Public URLs for immediate file access
4. **Organization**: Automatic folder structure with timestamps
5. **Backup**: Built-in redundancy with cloud storage
6. **CDN Ready**: Files can be cached and distributed globally

## Testing

Run the S3 service test to verify your configuration:

```bash
python test_s3_service.py
```

This will test:
- Environment variable configuration
- S3 service initialization
- Connection health
- File listing capabilities

## Error Handling

If S3 upload fails, the API will:
1. Log the error
2. Keep local temporary files as fallback
3. Return error details in the `s3_uploads` field
4. Still provide local file paths for immediate access

## Migration Notes

- **Backward Compatibility**: The API still generates all file types
- **Response Format**: File URLs are now public S3 URLs instead of local paths
- **Cleanup**: Local temporary files are automatically cleaned up after successful S3 upload
- **Fallback**: If S3 is unavailable, local files are preserved

## Example Usage

```python
import requests

# Generate worksheet
response = requests.get(
    "http://localhost:8000/generate-worksheet/",
    params={
        "lesson_id": "66c3b8f2a1234567890abcde",
        "output": "worksheet",
        "generate_pdf": True
    }
)

result = response.json()

if result.get("s3_uploads", {}).get("status") == "success":
    # Files are available in S3
    pdf_url = result["files"]["pdf_no_solutions"]
    print(f"PDF available at: {pdf_url}")
else:
    # Handle error or use local files
    print("S3 upload failed:", result.get("s3_uploads", {}).get("message"))
```

## Dependencies

Added to requirements:
- `boto3>=1.34.0` - AWS SDK for S3 operations

## Security

- All sensitive credentials are stored in environment variables
- Public URLs are read-only
- Files are organized by timestamp to prevent conflicts
- No sensitive data is exposed in URLs or logs
