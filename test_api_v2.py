#!/usr/bin/env python3
"""
Test script for the new QA Worksheet Generator API v2.0
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
TEST_DOCUMENT_UUID = "12345678-1234-1234-1234-123456789abc"

def test_endpoint(endpoint, description, method="GET", data=None):
    """Test an API endpoint and print results"""
    print(f"\n🔍 Testing: {description}")
    print(f"Endpoint: {method} {endpoint}")
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=30)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=30)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"✅ Success: {result.get('success', 'N/A')}")
                if 'api_version' in result:
                    print(f"API Version: {result['api_version']}")
                if 'endpoint' in result:
                    print(f"Endpoint: {result['endpoint']}")
                
                # Print first few keys of data
                if 'data' in result and isinstance(result['data'], dict):
                    keys = list(result['data'].keys())[:5]
                    print(f"Data keys: {keys}")
                    
            except json.JSONDecodeError:
                print("✅ Response received (not JSON)")
        else:
            print(f"❌ Failed: {response.status_code}")
            try:
                error = response.json()
                print(f"Error: {error}")
            except:
                print(f"Error text: {response.text[:200]}")
                
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Test failed: {e}")

def main():
    """Run all API tests"""
    print("🚀 Testing QA Worksheet Generator API v2.0")
    print("=" * 50)
    
    # Test API info endpoint
    test_endpoint("/api/v2/info", "API Information")
    
    # Test health check
    test_endpoint("/api/v2/status/health", "System Health Check")
    
    # Test PDF status
    test_endpoint("/api/v2/status/pdf", "PDF Conversion Status")
    
    # Test S3 status
    test_endpoint("/api/v2/status/s3", "S3 Storage Status")
    
    # Test document search
    test_endpoint("/api/v2/documents/search?query=test&limit=5", "Document Search")
    
    # Test mindmap search
    test_endpoint("/api/v2/mindmaps/search?query=test&limit=5", "Mindmap Search")
    
    # Test lesson search (legacy)
    test_endpoint("/api/v2/lessons/search?query=1&limit=5", "Lesson Search (Legacy)")
    
    # Test file listing
    test_endpoint("/api/v2/files/list?limit=10", "File Listing")
    
    # Test mindmap generation from JSON
    sample_mindmap = {
        "class": "go.TreeModel",
        "nodeDataArray": [
            {"key": 0, "text": "Root", "loc": "0 0", "brush": "gold"},
            {"key": 1, "parent": 0, "text": "Child 1", "dir": "right", "brush": "skyblue"},
            {"key": 2, "parent": 0, "text": "Child 2", "dir": "left", "brush": "palevioletred"}
        ]
    }
    test_endpoint("/api/v2/mindmaps/generate-from-json?title=test_mindmap", 
                 "Mindmap Generation from JSON", "POST", sample_mindmap)
    
    print("\n" + "=" * 50)
    print("🏁 API Tests Complete!")
    print("\nTo test document-specific endpoints, you need:")
    print("1. A valid document_uuid in the database")
    print("2. Run the server: py app.py")
    print("3. Access docs: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
