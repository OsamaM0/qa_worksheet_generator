#!/usr/bin/env python3
import uvicorn
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/app.log') if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

# Add the wheel package location to Python path
sys.path.insert(0, '/opt/venv/lib/python3.10/site-packages')

def main():
    try:
        logger.info("Starting worksheet generator application...")
        
        # Import the app dynamically
        import app
        application = getattr(app, 'app')
        
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', '8081'))
        
        logger.info(f"Starting worksheet API on {host}:{port}")
        print(f"Starting worksheet API on {host}:{port}")
        
        uvicorn.run(
            application, 
            host=host, 
            port=port,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        error_msg = f"Error starting application: {e}"
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
