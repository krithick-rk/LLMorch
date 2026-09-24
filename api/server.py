#!/usr/bin/env python3
"""
LLMorch API server entry point.
Starts the FastAPI application via uvicorn.
Usage:
    python3 -m api.server
    python3 -m api.server --host 127.0.0.1 --port 8000
"""

import os
import sys
import argparse

def main():
    try:
        import uvicorn
    except ImportError:
        print("[ERROR] uvicorn not found. Install with: pip install uvicorn")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="LLMorch Analyst Console API Server")
    parser.add_argument(
        "--host",
        default=os.environ.get("LLMORCH_API_HOST", "127.0.0.1"),
        help="Bind host (default: 127.0.0.1 — localhost only)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LLMORCH_API_PORT", "8000")),
        help="Bind port (default: 8000)"
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    # Ensure project root is in sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
