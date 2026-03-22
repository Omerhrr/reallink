#!/usr/bin/env python3
"""
RealLink Ecosystem - Frontend Runner
Flask server with auto-reload for development
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def main():
    """Run the Flask frontend server"""
    from app import app

    # Get configuration from environment
    host = os.getenv("FRONTEND_HOST", "0.0.0.0")
    port = int(os.getenv("FRONTEND_PORT", 5000))
    debug = os.getenv("DEBUG", "true").lower() == "true"

    print("=" * 50)
    print("  RealLink Ecosystem - Frontend Server")
    print("=" * 50)
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Debug: {debug}")
    print(f"  URL: http://localhost:{port}")
    print("=" * 50)
    print()

    # Run Flask server
    app.run(
        host=host,
        port=port,
        debug=debug
    )


if __name__ == "__main__":
    main()
