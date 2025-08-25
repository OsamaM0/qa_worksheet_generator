#!/usr/bin/env python3
import uvicorn
import os
import sys
import logging

# Configure logging with better error handling
def setup_logging():
    """Setup logging with fallback if file logging fails."""
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Try to add file handler, but don't fail if it doesn't work
    try:
        logs_dir = '/app/logs'
        if os.path.exists(logs_dir):
            # Test if we can write to the logs directory
            test_file = os.path.join(logs_dir, 'test.log')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                # If we got here, we can write to the directory
                handlers.append(logging.FileHandler('/app/logs/app.log'))
            except (PermissionError, OSError):
                print("Warning: Cannot write to /app/logs - logging to console only")
    except Exception as e:
        print(f"Warning: Logging setup issue: {e} - logging to console only")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)

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
