#!/usr/bin/env python3
"""
RealLink Ecosystem - Backend Runner
FastAPI server with auto-reload for development
"""

import os
import sys
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def main():
    """Run the FastAPI backend server"""
    # Get configuration from environment
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    reload = os.getenv("DEBUG", "true").lower() == "true"

    print("=" * 50)
    print("  RealLink Ecosystem - Backend Server")
    print("=" * 50)
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Reload: {reload}")
    print(f"  API Docs: http://localhost:{port}/docs")
    print("=" * 50)
    print()

    # Run uvicorn server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
