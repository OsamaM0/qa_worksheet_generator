#!/usr/bin/env python3
"""
Test script to check which packages are actually required for the application to start.
Run this to see what's missing before Docker build.
"""

import sys

def test_import(package_name, import_name=None):
    """Test if a package can be imported."""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"✅ {package_name}: OK")
        return True
    except ImportError as e:
        print(f"❌ {package_name}: MISSING - {e}")
        return False

def main():
    print("Testing required packages for QA Worksheet Generator...")
    print("=" * 50)
    
    # Core packages (absolutely required)
    core_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pymongo", "pymongo"),
        ("python-docx", "docx"),
        ("requests", "requests"),
        ("python-dotenv", "dotenv"),
    ]
    
    # Optional packages (nice to have)
    optional_packages = [
        ("reportlab", "reportlab"),
        ("PyPDF2", "PyPDF2"),
        ("arabic-reshaper", "arabic_reshaper"),
        ("python-bidi", "bidi"),
        ("Pillow", "PIL"),
        ("tqdm", "tqdm"),
    ]
    
    print("Core packages (required):")
    core_missing = 0
    for pkg, imp in core_packages:
        if not test_import(pkg, imp):
            core_missing += 1
    
    print("\nOptional packages:")
    optional_missing = 0
    for pkg, imp in optional_packages:
        if not test_import(pkg, imp):
            optional_missing += 1
    
    print("\n" + "=" * 50)
    print(f"Summary:")
    print(f"Core packages missing: {core_missing}/{len(core_packages)}")
    print(f"Optional packages missing: {optional_missing}/{len(optional_packages)}")
    
    if core_missing == 0:
        print("🎉 All core packages available! App should work.")
    else:
        print("⚠️  Some core packages missing. App may not work properly.")
        
    print("\nTo install missing packages:")
    print("pip install fastapi uvicorn pymongo python-docx requests python-dotenv")

if __name__ == "__main__":
    main()
