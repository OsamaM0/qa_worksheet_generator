"""
Test script for S3 service
Tests the S3/R2 connection and basic functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_s3_configuration():
    """Test S3 configuration from environment variables"""
    print("=== S3 Configuration Test ===")
    
    required_vars = [
        'S3_ACCESS_KEY_ID',
        'S3_SECRET_ACCESS_KEY', 
        'S3_ENDPOINT',
        'S3_BUCKET_NAME'
    ]
    
    print("Checking environment variables...")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if 'KEY' in var or 'SECRET' in var:
                print(f"✓ {var}: {'*' * len(value[:4])}{'*' * (len(value) - 8)}{value[-4:]}")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: Not set")
            return False
    
    return True

def test_s3_service():
    """Test S3 service initialization and health check"""
    print("\n=== S3 Service Test ===")
    
    try:
        # Try to import and initialize the S3 service
        from s3_service import S3Service
        
        print("Creating S3 service...")
        s3_service = S3Service()
        print("✓ S3 service initialized successfully")
        
        print("Running health check...")
        health = s3_service.health_check()
        print(f"Health check result: {health}")
        
        if health.get('status') == 'healthy':
            print("✓ S3 service is healthy")
            return True
        else:
            print("✗ S3 service is not healthy")
            return False
            
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure boto3 is installed: pip install boto3")
        return False
    except Exception as e:
        print(f"✗ S3 service error: {e}")
        return False

def test_s3_integration():
    """Test S3 integration functions"""
    print("\n=== S3 Integration Test ===")
    
    try:
        from s3_service import get_s3_service, upload_worksheet_files
        
        print("Testing S3 service getter...")
        service = get_s3_service()
        print("✓ S3 service getter works")
        
        # Test file listing
        print("Testing file listing...")
        files = service.list_files(max_keys=5)
        print(f"File listing result: {files}")
        
        if files.get('status') == 'success':
            print(f"✓ Found {files.get('count', 0)} files in bucket")
            return True
        else:
            print("✗ File listing failed")
            return False
            
    except Exception as e:
        print(f"✗ Integration test error: {e}")
        return False

def main():
    """Run all S3 tests"""
    print("Starting S3 Service Tests...")
    print("=" * 50)
    
    # Test 1: Configuration
    config_ok = test_s3_configuration()
    
    if not config_ok:
        print("\n❌ Configuration test failed. Please check your .env file.")
        return False
    
    # Test 2: Service initialization
    service_ok = test_s3_service()
    
    if not service_ok:
        print("\n❌ Service test failed. Please check your S3 credentials and network.")
        return False
    
    # Test 3: Integration
    integration_ok = test_s3_integration()
    
    if not integration_ok:
        print("\n❌ Integration test failed.")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All S3 tests passed! Your S3 service is ready.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
