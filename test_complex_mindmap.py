#!/usr/bin/env python3
"""
Quick test for the improved mindmap service
"""

import json
from mindmap_service import get_mindmap_service

def test_complex_mindmap():
    """Test with the complex mindmap data from main_image.py"""
    print("=== Testing Complex Mindmap Generation ===")
    
    try:
        service = get_mindmap_service()
        
        # Test with the complex sample data (same as main_image.py)
        sample_data = service.create_sample_mindmap_data()
        print(f"Sample data has {len(sample_data['nodeDataArray'])} nodes")
        
        # Show some node details
        for i, node in enumerate(sample_data['nodeDataArray'][:5]):
            print(f"  Node {i}: {node.get('text', 'No text')} (key: {node.get('key')}, parent: {node.get('parent', 'None')})")
        
        print("\nAttempting image generation...")
        result = service.generate_image_from_json(
            mindmap_json=sample_data,
            title="complex_test_mindmap",
            width=1200,
            height=800
        )
        
        if result["status"] == "success":
            print("✓ Complex mindmap generated successfully!")
            print(f"  Public URL: {result['public_url']}")
            print(f"  File size: {result['file_size']} bytes")
        else:
            print(f"✗ Complex mindmap generation failed: {result['message']}")
            if 'upload_error' in result:
                print(f"  Upload error: {result['upload_error']}")
        
        return result
        
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_complex_mindmap()
