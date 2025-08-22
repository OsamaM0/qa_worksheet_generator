#!/usr/bin/env python3
"""
Test script for the Saudi Edu Worksheet Generator API
"""

import requests
import json
import time

def test_api_endpoint(base_url="http://localhost:8000"):
    """Test the worksheet generator API"""
    
    print("🧪 Testing Saudi Edu Worksheet Generator API")
    print(f"📍 Base URL: {base_url}")
    print("-" * 50)
    
    # Test cases
    test_cases = [
        {
            "name": "Question Bank without PDF",
            "params": {
                "lesson_id": 600,
                "output": "question_bank",
                "num_questions": 2,
                "generate_pdf": False
            }
        },
        {
            "name": "Worksheet with PDF",
            "params": {
                "lesson_id": 600,
                "output": "worksheet",
                "num_questions": 3,
                "generate_pdf": True
            }
        },
        {
            "name": "All Questions with PDF",
            "params": {
                "lesson_id": 600,
                "output": "question_bank",
                "num_questions": 0,
                "generate_pdf": True
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test {i}: {test_case['name']}")
        
        try:
            response = requests.get(
                f"{base_url}/generate-worksheet/",
                params=test_case['params'],
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"   📄 Lesson: {result.get('lesson_title', 'N/A')}")
                print(f"   📁 Files generated: {len(result.get('files', {}))}")
                
                files = result.get('files', {})
                for file_type, file_path in files.items():
                    if file_path and not file_type.endswith('_error'):
                        print(f"   📄 {file_type}: ✓")
                    elif file_type.endswith('_error'):
                        print(f"   ❌ {file_type}: {file_path}")
                
                if 'generate_pdf' in result:
                    print(f"   🔄 PDF Generation: {'Enabled' if result['generate_pdf'] else 'Disabled'}")
                    
            else:
                print(f"❌ Failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection Error: {e}")
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Test completed!")

def test_health_check(base_url="http://localhost:8000"):
    """Test if the API is accessible"""
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy and accessible")
            return True
        else:
            print(f"⚠️ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Saudi Edu Worksheet Generator - API Test")
    print("=" * 50)
    
    # Health check first
    if test_health_check():
        # Run API tests
        test_api_endpoint()
    else:
        print("❌ Cannot proceed with tests - API is not accessible")
        print("💡 Make sure the application is running on http://localhost:8000")
