#!/usr/bin/env python3
import uvicorn
import os
import sys
from pathlib import Path

# Add the wheel package location to Python path
sys.path.insert(0, '/opt/venv/lib/python3.10/site-packages')

def main():
    try:
        # Import the app dynamically
        import app
        application = getattr(app, 'app')
        
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', '8000'))
        
        print(f"Starting worksheet API on {host}:{port}")
        uvicorn.run(application, host=host, port=port)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
