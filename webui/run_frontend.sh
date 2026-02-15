#!/bin/bash
# Run only the frontend dev server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NODE_BIN_DIR="$PROJECT_ROOT/.tools/node/bin"

chmod +x "$SCRIPT_DIR/setup_node.sh"
"$SCRIPT_DIR/setup_node.sh"
export PATH="$NODE_BIN_DIR:$PATH"
cd "$SCRIPT_DIR/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Starting frontend dev server on http://localhost:5173"
npm run dev
