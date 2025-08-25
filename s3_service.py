"""
S3 Service for Cloudflare R2 Integration
Handles file uploads to Cloudflare R2 storage
"""

import boto3
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class S3Service:
    """Service for handling S3/R2 file operations"""
    
    def __init__(self):
        """Initialize S3 client with Cloudflare R2 configuration"""
        self.access_key_id = os.getenv('S3_ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
        self.endpoint_url = os.getenv('S3_ENDPOINT')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
        if not all([self.access_key_id, self.secret_access_key, self.endpoint_url, self.bucket_name]):
            raise ValueError("Missing required S3 configuration. Check your .env file.")
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                endpoint_url=self.endpoint_url,
                region_name='auto'  # Cloudflare R2 uses 'auto' for region
            )
            
            # Test connection
            self._test_connection()
            logger.info("S3 service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def _test_connection(self) -> bool:
        """Test S3 connection by attempting to list objects"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404':
                logger.error(f"Bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                logger.error(f"Access denied to bucket '{self.bucket_name}'")
            else:
                logger.error(f"Error accessing bucket: {error_code}")
            raise
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    def upload_file(self, 
                   local_file_path: str, 
                   s3_key: Optional[str] = None,
                   content_type: Optional[str] = None,
                   metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Upload a file to S3/R2
        
        Args:
            local_file_path: Path to the local file
            s3_key: S3 object key (auto-generated if None)
            content_type: MIME type (auto-detected if None)
            metadata: Additional metadata for the object
        
        Returns:
            Dictionary with upload results
        """
        try:
            if not os.path.exists(local_file_path):
                raise FileNotFoundError(f"Local file not found: {local_file_path}")
            
            # Generate S3 key if not provided
            if s3_key is None:
                file_extension = os.path.splitext(local_file_path)[1]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = str(uuid.uuid4())[:8]
                s3_key = f"worksheets/{timestamp}_{unique_id}{file_extension}"
            
            # Detect content type if not provided
            if content_type is None:
                content_type = self._get_content_type(local_file_path)
            
            # Prepare upload arguments
            upload_args = {
                'ContentType': content_type,
            }
            
            if metadata:
                upload_args['Metadata'] = metadata
            
            # Get file size
            file_size = os.path.getsize(local_file_path)
            
            # Upload file
            logger.info(f"Uploading {local_file_path} to s3://{self.bucket_name}/{s3_key}")
            
            self.s3_client.upload_file(
                local_file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs=upload_args
            )
            
            # Generate public URL
            public_url = f"{self.endpoint_url.replace('dcdb150a91310324ecc43b417e14446b.r2.cloudflarestorage.com', 'pub-dcdb150a91310324ecc43b417e14446b.r2.dev')}/{s3_key}"
            
            logger.info(f"Successfully uploaded file to: {public_url}")
            
            return {
                "status": "success",
                "s3_key": s3_key,
                "bucket": self.bucket_name,
                "public_url": public_url,
                "file_size": file_size,
                "content_type": content_type,
                "upload_time": datetime.now().isoformat()
            }
            
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return {"status": "error", "message": str(e)}
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return {"status": "error", "message": "AWS credentials not configured"}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"S3 ClientError [{error_code}]: {error_message}")
            return {"status": "error", "message": f"S3 error: {error_message}"}
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def upload_multiple_files(self, 
                            file_paths: Dict[str, str],
                            folder_prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload multiple files to S3/R2
        
        Args:
            file_paths: Dictionary mapping file types to local paths
            folder_prefix: Optional folder prefix for all files
        
        Returns:
            Dictionary with upload results for all files
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        if folder_prefix:
            base_key = f"{folder_prefix}/{timestamp}_{unique_id}"
        else:
            base_key = f"worksheets/{timestamp}_{unique_id}"
        
        results = {
            "status": "success",
            "files": {},
            "errors": {},
            "upload_time": datetime.now().isoformat(),
            "folder": base_key
        }
        
        for file_type, local_path in file_paths.items():
            if os.path.exists(local_path):
                file_extension = os.path.splitext(local_path)[1]
                s3_key = f"{base_key}/{file_type}{file_extension}"
                
                upload_result = self.upload_file(local_path, s3_key)
                
                if upload_result["status"] == "success":
                    results["files"][file_type] = upload_result
                else:
                    results["errors"][file_type] = upload_result["message"]
                    results["status"] = "partial"
            else:
                results["errors"][file_type] = f"File not found: {local_path}"
                results["status"] = "partial"
        
        if len(results["files"]) == 0:
            results["status"] = "error"
        
        return results
    
    def delete_file(self, s3_key: str) -> Dict[str, Any]:
        """
        Delete a file from S3/R2
        
        Args:
            s3_key: S3 object key to delete
        
        Returns:
            Dictionary with deletion result
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted s3://{self.bucket_name}/{s3_key}")
            return {"status": "success", "message": f"File deleted: {s3_key}"}
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"S3 ClientError [{error_code}]: {error_message}")
            return {"status": "error", "message": f"Delete error: {error_message}"}
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def list_files(self, prefix: str = "", max_keys: int = 100) -> Dict[str, Any]:
        """
        List files in the bucket
        
        Args:
            prefix: Filter objects by prefix
            max_keys: Maximum number of objects to return
        
        Returns:
            Dictionary with file listing
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'etag': obj['ETag'].strip('"')
                    })
            
            return {
                "status": "success",
                "files": files,
                "count": len(files),
                "truncated": response.get('IsTruncated', False)
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"S3 ClientError [{error_code}]: {error_message}")
            return {"status": "error", "message": f"List error: {error_message}"}
        except Exception as e:
            logger.error(f"List failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_file_info(self, s3_key: str) -> Dict[str, Any]:
        """
        Get information about a file in S3/R2
        
        Args:
            s3_key: S3 object key
        
        Returns:
            Dictionary with file information
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            
            return {
                "status": "success",
                "key": s3_key,
                "size": response['ContentLength'],
                "content_type": response.get('ContentType', 'unknown'),
                "last_modified": response['LastModified'].isoformat(),
                "etag": response['ETag'].strip('"'),
                "metadata": response.get('Metadata', {})
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404':
                return {"status": "error", "message": "File not found"}
            else:
                error_message = e.response.get('Error', {}).get('Message', str(e))
                return {"status": "error", "message": f"Info error: {error_message}"}
        except Exception as e:
            logger.error(f"Get info failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_content_type(self, file_path: str) -> str:
        """
        Determine content type based on file extension
        
        Args:
            file_path: Path to the file
        
        Returns:
            MIME content type
        """
        extension = os.path.splitext(file_path)[1].lower()
        
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.json': 'application/json',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.zip': 'application/zip',
            '.xml': 'application/xml'
        }
        
        return content_types.get(extension, 'application/octet-stream')
    
    def get_public_url(self, s3_key: str) -> str:
        """
        Generate public URL for an S3 object
        
        Args:
            s3_key: S3 object key
        
        Returns:
            Public URL string
        """
        # For Cloudflare R2, convert storage endpoint to public endpoint
        public_endpoint = self.endpoint_url.replace(
            'dcdb150a91310324ecc43b417e14446b.r2.cloudflarestorage.com',
            'pub-dcdb150a91310324ecc43b417e14446b.r2.dev'
        )
        return f"{public_endpoint}/{s3_key}"
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check S3 service health
        
        Returns:
            Dictionary with health status
        """
        try:
            # Test bucket access
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            # Test listing (limit to 1 object)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            
            return {
                "status": "healthy",
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "accessible": True,
                "object_count": response.get('KeyCount', 0)
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            return {
                "status": "unhealthy",
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "accessible": False,
                "error": error_code,
                "message": str(e)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "accessible": False,
                "error": "connection_failed",
                "message": str(e)
            }


# Singleton instance
_s3_service = None

def get_s3_service() -> S3Service:
    """Get singleton S3 service instance"""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service


# Convenience functions
def upload_file_to_s3(local_path: str, s3_key: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to upload a single file"""
    service = get_s3_service()
    return service.upload_file(local_path, s3_key)


def upload_worksheet_files(files: Dict[str, str], lesson_title: str = "") -> Dict[str, Any]:
    """Convenience function to upload worksheet files"""
    service = get_s3_service()
    
    # Create folder prefix based on lesson title
    if lesson_title:
        # Clean lesson title for folder name
        import re
        clean_title = re.sub(r'[<>:"/\\|?*]', '_', lesson_title)
        folder_prefix = f"worksheets/{clean_title}"
    else:
        folder_prefix = "worksheets"
    
    return service.upload_multiple_files(files, folder_prefix)


if __name__ == "__main__":
    # Test the S3 service
    try:
        service = S3Service()
        health = service.health_check()
        print(f"S3 Service Health: {health}")
        
        # List some files
        files = service.list_files(max_keys=5)
        print(f"Files: {files}")
        
    except Exception as e:
        print(f"S3 Service Error: {e}")
