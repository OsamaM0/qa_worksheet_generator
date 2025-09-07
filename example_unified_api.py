#!/usr/bin/env python3
"""
Example usage of the unified create-all endpoint
"""

import requests
import json
import uuid

# Configuration
BASE_URL = "http://localhost:8000"

def generate_test_uuid():
    """Generate a test UUID"""
    return str(uuid.uuid4())

def create_all_documents_example():
    """Example of using the unified create-all endpoint"""
    
    # Generate a test UUID
    test_uuid = generate_test_uuid()
    print(f"Using test UUID: {test_uuid}")
    
    # Endpoint URL
    url = f"{BASE_URL}/api/v2/create-all"
    
    # Parameters
    params = {
        "document_uuid": test_uuid,
        "override": False,  # Set to True to regenerate if exists
        "output": "worksheet",  # or "question_bank"
        "multiple_choice_count": 5,  # Limit to 5 multiple choice questions
        "true_false_count": 3,  # Limit to 3 true/false questions
        "short_answer_count": 2,  # Limit to 2 short answer questions
        "complete_count": 2,  # Limit to 2 fill-in-blank questions
        "mindmap_width": 1600,  # Larger mindmap
        "mindmap_height": 1000,
        "generate_pdf": True,
        "html_parsing": False
    }
    
    print(f"\n🚀 Creating all documents for UUID: {test_uuid}")
    print("Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    
    try:
        # Make the request
        response = requests.post(url, params=params, timeout=60)
        
        print(f"\n📡 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ Success: {result.get('success', False)}")
            print(f"API Version: {result.get('api_version', 'N/A')}")
            
            data = result.get('data', {})
            
            if result.get('success'):
                print(f"\n📁 Folder Path: {data.get('folder_path', 'N/A')}")
                
                # Show created files
                created_files = data.get('created_files', {})
                if created_files:
                    print(f"\n📄 Created Files:")
                    for file_type, files in created_files.items():
                        print(f"  {file_type.upper()}:")
                        if isinstance(files, dict):
                            for file_key, file_info in files.items():
                                print(f"    - {file_info.get('standard_name', file_key)}")
                                print(f"      URL: {file_info.get('public_url', 'N/A')}")
                        else:
                            print(f"    - {files.get('standard_name', 'File')}")
                            print(f"      URL: {files.get('public_url', 'N/A')}")
                
                # Show any errors
                errors = data.get('errors', {})
                if errors:
                    print(f"\n❌ Errors:")
                    for error_type, error_msg in errors.items():
                        print(f"  {error_type}: {error_msg}")
                
                # Show summary
                summary = data.get('summary', {})
                if summary:
                    print(f"\n📊 Summary:")
                    print(f"  Success Rate: {summary.get('success_rate', 'N/A')}")
                    print(f"  Successfully Created: {summary.get('successfully_created', 0)}")
                    print(f"  Failed: {summary.get('failed', 0)}")
                
            else:
                print(f"\n❌ Failed: {data.get('error', 'Unknown error')}")
                
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            try:
                error = response.json()
                print(f"Error details: {json.dumps(error, indent=2)}")
            except:
                print(f"Error text: {response.text}")
                
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_existing_documents_example():
    """Example of checking for existing documents"""
    
    # Use a fixed UUID to test override functionality
    test_uuid = "12345678-1234-1234-1234-123456789abc"
    
    url = f"{BASE_URL}/api/v2/create-all"
    params = {
        "document_uuid": test_uuid,
        "override": False  # Check if exists without creating
    }
    
    print(f"\n🔍 Checking for existing documents: {test_uuid}")
    
    try:
        response = requests.post(url, params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            data = result.get('data', {})
            
            if data.get('exists'):
                print("✅ Documents exist!")
                print(f"Folder: {data.get('folder_path')}")
                
                existing_data = data.get('existing_data', {})
                print(f"Worksheet in DB: {existing_data.get('worksheet_in_db', False)}")
                print(f"Questions in DB: {existing_data.get('questions_in_db', False)}")
                print(f"Mindmap in DB: {existing_data.get('mindmap_in_db', False)}")
                print(f"Files in S3: {len(existing_data.get('files_in_s3', []))}")
                
                print("\n💡 To override existing documents, use override=true")
                
            else:
                print("📝 No existing documents found - would create new ones")
                
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run examples"""
    print("🧪 QA Worksheet Generator API v2.0 - Unified Endpoint Examples")
    print("=" * 70)
    
    print("\n1️⃣ Checking for existing documents:")
    check_existing_documents_example()
    
    print("\n" + "=" * 70)
    print("\n2️⃣ Creating all documents (new UUID):")
    create_all_documents_example()
    
    print("\n" + "=" * 70)
    print("🏁 Examples Complete!")
    print("\nNote: These examples require:")
    print("1. Server running: py app.py")
    print("2. Valid documents in the database")
    print("3. Working S3/MongoDB connections")

if __name__ == "__main__":
    main()
