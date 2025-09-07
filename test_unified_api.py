#!/usr/bin/env python3
"""
Test script for the new unified API structure
Tests the create-all endpoint and folder structure
"""

import requests
import json
import time
from datetime import datetime

# API base URL - update this to match your server
BASE_URL = "http://localhost:8000"

def test_api_info():
    """Test the API info endpoint"""
    print("=== Testing API Info ===")
    try:
        response = requests.get(f"{BASE_URL}/api/v2/info")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Version: {data['api_version']}")
            print(f"✅ Title: {data['title']}")
            print(f"✅ Groups: {list(data['endpoint_groups'].keys())}")
        else:
            print(f"❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()

def test_health_check():
    """Test the health check endpoint"""
    print("=== Testing Health Check ===")
    try:
        response = requests.get(f"{BASE_URL}/api/v2/status/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health Status: {data['data']['overall_status']}")
            print(f"✅ Success: {data['success']}")
            
            services = data['data']['services']
            for service, status in services.items():
                print(f"  - {service}: {status.get('status', 'unknown')}")
        else:
            print(f"❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()

def test_search_documents():
    """Test document search to find a valid UUID"""
    print("=== Testing Document Search ===")
    try:
        response = requests.get(f"{BASE_URL}/api/v2/documents/search", 
                              params={"query": "lesson", "limit": 5})
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {data['data']['total_results']} documents")
            
            if data['data']['results']:
                # Return the first document UUID for testing
                first_doc = data['data']['results'][0]
                print(f"✅ First document: {first_doc['document_uuid']}")
                print(f"  - Filename: {first_doc['filename']}")
                print(f"  - Type: {first_doc['type']}")
                return first_doc['document_uuid']
            else:
                print("❌ No documents found")
                return None
        else:
            print(f"❌ Failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    print()

def test_create_all_endpoint(document_uuid, override=False):
    """Test the unified create-all endpoint"""
    print(f"=== Testing Create-All Endpoint (UUID: {document_uuid}) ===")
    
    if not document_uuid:
        print("❌ No document UUID provided")
        return
    
    try:
        params = {
            "document_uuid": document_uuid,
            "override": override,
            "mindmap_width": 800,
            "mindmap_height": 600,
            "generate_pdf": True
        }
        
        print(f"📝 Request params: {params}")
        
        response = requests.post(f"{BASE_URL}/api/v2/create-all", params=params)
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data['success']}")
            print(f"✅ API Version: {data['api_version']}")
            
            result_data = data['data']
            print(f"✅ Document UUID: {result_data['document_uuid']}")
            print(f"✅ Folder Path: {result_data['folder_path']}")
            print(f"✅ Status: {result_data['status']}")
            
            if 'existing_files' in result_data:
                print("📁 Existing files found:")
                for file_type, url in result_data['existing_files'].items():
                    print(f"  - {file_type}: {url}")
                print("💡 Use override=true to regenerate")
            
            if 'created_files' in result_data:
                print("📁 Created files:")
                for file_type, file_info in result_data['created_files'].items():
                    print(f"  - {file_type}: {file_info['public_url']}")
                    print(f"    Type: {file_info['type']}, Format: {file_info['format']}")
            
            if 'errors' in result_data:
                print("❌ Errors:")
                for error_type, error_msg in result_data['errors'].items():
                    print(f"  - {error_type}: {error_msg}")
            
            if 'summary' in result_data:
                summary = result_data['summary']
                print(f"📊 Summary: {summary['success_rate']} created successfully")
                
            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    print()

def test_mindmap_endpoint(document_uuid):
    """Test the mindmap generation endpoint"""
    print(f"=== Testing Mindmap Endpoint (UUID: {document_uuid}) ===")
    
    if not document_uuid:
        print("❌ No document UUID provided")
        return
    
    try:
        params = {
            "document_uuid": document_uuid,
            "width": 800,
            "height": 600
        }
        
        response = requests.get(f"{BASE_URL}/api/v2/mindmaps/generate", params=params)
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data['success']}")
            
            if data['success']:
                mindmap_data = data['data']
                if 'public_url' in mindmap_data:
                    print(f"✅ Mindmap URL: {mindmap_data['public_url']}")
                if 's3_key' in mindmap_data:
                    print(f"✅ S3 Key: {mindmap_data['s3_key']}")
            else:
                print(f"❌ Generation failed: {data['data'].get('message', 'Unknown error')}")
                
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"❌ Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    print()

def main():
    """Run all tests"""
    print("🚀 Starting Unified API Tests")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    print(f"🌐 Base URL: {BASE_URL}")
    print("=" * 50)
    
    # Test basic endpoints
    test_api_info()
    test_health_check()
    
    # Find a document to test with
    document_uuid = test_search_documents()
    
    if document_uuid:
        # Test mindmap generation
        test_mindmap_endpoint(document_uuid)
        
        # Test create-all endpoint (first without override)
        result1 = test_create_all_endpoint(document_uuid, override=False)
        
        # If files exist, test with override
        if result1 and result1.get('data', {}).get('exists'):
            print("🔄 Testing with override=true...")
            time.sleep(2)  # Brief pause
            test_create_all_endpoint(document_uuid, override=True)
    
    print("=" * 50)
    print("✅ Test suite completed!")

if __name__ == "__main__":
    main()
