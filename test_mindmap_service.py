#!/usr/bin/env python3
"""
Test script for mindmap functionality
"""

import json
import asyncio
from mindmap_service import MindMapService, get_mindmap_service

def test_mindmap_service():
    """Test the mindmap service functionality"""
    print("=== Testing Mindmap Service ===")
    
    try:
        # Initialize service
        service = get_mindmap_service()
        print("✓ Mindmap service initialized successfully")
        
        # Test with sample data
        print("\n--- Testing with sample data ---")
        sample_data = service.create_sample_mindmap_data()
        print(f"✓ Sample data created with {len(sample_data['nodeDataArray'])} nodes")
        
        # Load sample mindmap from file
        print("\n--- Testing with file data ---")
        try:
            with open('sample_mindmap.json', 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            print(f"✓ File data loaded with {len(file_data['nodeDataArray'])} nodes")
        except FileNotFoundError:
            print("⚠ sample_mindmap.json not found, using sample data")
            file_data = sample_data
        
        # Test image generation (this requires S3 to be configured)
        print("\n--- Testing image generation ---")
        print("Note: This test requires S3 configuration to complete successfully")
        
        try:
            result = service.generate_image_from_json(
                mindmap_json=file_data,
                title="test_mindmap_generation",
                width=800,
                height=600
            )
            
            if result["status"] == "success":
                print("✓ Image generated and uploaded successfully!")
                print(f"  Public URL: {result['public_url']}")
                print(f"  S3 Key: {result['s3_key']}")
                print(f"  File Size: {result['file_size']} bytes")
            else:
                print(f"✗ Image generation failed: {result['message']}")
                
        except Exception as e:
            print(f"✗ Image generation error: {e}")
            print("  This is expected if S3 is not configured or Playwright browser is not set up")
        
        print("\n=== Mindmap Service Test Complete ===")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mindmap_service()
