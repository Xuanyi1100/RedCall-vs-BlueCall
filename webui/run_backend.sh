#!/bin/bash
# Run only the backend server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"

echo "Starting backend server on http://localhost:8000"
uv run python server.py
