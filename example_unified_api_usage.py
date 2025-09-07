#!/usr/bin/env python3
"""
Example usage of the Unified API v2.0
Shows how to use the new create-all endpoint
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
DOCUMENT_UUID = "your-document-uuid-here"  # Replace with actual UUID

def create_complete_package(document_uuid, override=False):
    """
    Create mindmap, worksheet, and question bank for a document
    """
    print(f"🚀 Creating complete package for document: {document_uuid}")
    
    # Prepare request
    url = f"{BASE_URL}/api/v2/create-all"
    params = {
        "document_uuid": document_uuid,
        "override": override,
        "mindmap_width": 1200,
        "mindmap_height": 800,
        "multiple_choice_count": -1,  # Include all multiple choice questions
        "true_false_count": -1,       # Include all true/false questions  
        "short_answer_count": -1,     # Include all short answer questions
        "complete_count": -1,         # Include all complete questions
        "generate_pdf": True,
        "html_parsing": False
    }
    
    try:
        # Make request
        response = requests.post(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                
                print(f"✅ Status: {result['status']}")
                print(f"📁 Folder: {result['folder_path']}")
                
                # Check if files already exist
                if result.get('exists'):
                    print("📋 Files already exist:")
                    for file_type, url in result['existing_files'].items():
                        print(f"  - {file_type}: {url}")
                    print("💡 Use override=True to regenerate")
                    return result
                
                # Show created files
                if 'created_files' in result:
                    print("📋 Created files:")
                    for file_type, file_info in result['created_files'].items():
                        print(f"  - {file_type} ({file_info['format']}): {file_info['public_url']}")
                
                # Show any errors
                if 'errors' in result and result['errors']:
                    print("❌ Errors occurred:")
                    for error_type, error_msg in result['errors'].items():
                        print(f"  - {error_type}: {error_msg}")
                
                # Show summary
                if 'summary' in result:
                    summary = result['summary']
                    print(f"📊 Summary: {summary['success_rate']} files created successfully")
                
                return result
            else:
                print(f"❌ Request failed: {data.get('error', 'Unknown error')}")
                return None
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def search_for_document(query="lesson"):
    """
    Search for documents to find a valid UUID for testing
    """
    print(f"🔍 Searching for documents with query: '{query}'")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/documents/search",
            params={"query": query, "limit": 5}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success'] and data['data']['results']:
                print(f"✅ Found {data['data']['total_results']} documents:")
                
                for i, doc in enumerate(data['data']['results'], 1):
                    print(f"  {i}. UUID: {doc['document_uuid']}")
                    print(f"     File: {doc['filename']}")
                    print(f"     Type: {doc['type']}")
                    print()
                
                # Return first document UUID
                return data['data']['results'][0]['document_uuid']
            else:
                print("❌ No documents found")
                return None
        else:
            print(f"❌ Search failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Search error: {e}")
        return None

def check_api_health():
    """
    Check if the API is healthy and ready
    """
    print("🏥 Checking API health...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/status/health")
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                print("✅ API is healthy")
                
                services = data['data']['services']
                for service, status in services.items():
                    status_emoji = "✅" if status.get('status') == 'healthy' else "❌"
                    print(f"  {status_emoji} {service}: {status.get('status', 'unknown')}")
                
                return True
            else:
                print(f"❌ API is unhealthy: {data['data'].get('overall_status')}")
                return False
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def main():
    """
    Main example workflow
    """
    print("=" * 60)
    print("🎯 Unified API v2.0 - Complete Package Creation Example")
    print("=" * 60)
    
    # 1. Check API health
    if not check_api_health():
        print("💔 API is not healthy. Please check the server.")
        return
    
    print()
    
    # 2. Find a document to work with
    document_uuid = search_for_document()
    
    if not document_uuid:
        print("🤷 No documents found. Please make sure you have documents in the database.")
        print("💡 You can also set DOCUMENT_UUID variable at the top of this script.")
        return
    
    print()
    
    # 3. Create complete package (first attempt - may find existing files)
    print("🎯 First attempt (checking for existing files)...")
    result1 = create_complete_package(document_uuid, override=False)
    
    print()
    
    # 4. If files exist, demonstrate override functionality
    if result1 and result1.get('exists'):
        print("🔄 Files exist, demonstrating override functionality...")
        user_input = input("Do you want to regenerate files? (y/N): ").lower().strip()
        
        if user_input == 'y':
            create_complete_package(document_uuid, override=True)
        else:
            print("✅ Keeping existing files")
    
    print()
    print("=" * 60)
    print("✅ Example completed! ")
    print("💡 Check the generated URLs to download your files.")
    print("=" * 60)

if __name__ == "__main__":
    main()
