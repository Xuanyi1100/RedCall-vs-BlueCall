#!/bin/bash
# Install a project-local Node.js runtime (no system-wide changes)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TOOLS_DIR="$PROJECT_ROOT/.tools"
NODE_VERSION="v20.19.0"
NODE_ARCH="linux-x64"
NODE_DIST="node-${NODE_VERSION}-${NODE_ARCH}"
NODE_DIR="$TOOLS_DIR/$NODE_DIST"
NODE_BIN_DIR="$TOOLS_DIR/node/bin"

mkdir -p "$TOOLS_DIR"

if [ ! -d "$NODE_DIR" ]; then
  echo "Installing local Node.js ${NODE_VERSION}..."
  cd "$TOOLS_DIR"
  curl -fsSLO "https://nodejs.org/dist/${NODE_VERSION}/${NODE_DIST}.tar.xz"
  tar -xf "${NODE_DIST}.tar.xz"
fi

ln -sfn "$NODE_DIR" "$TOOLS_DIR/node"

if [ ! -x "$NODE_BIN_DIR/node" ]; then
  echo "Failed to prepare local Node runtime at $NODE_BIN_DIR"
  exit 1
fi

echo "Local Node ready:"
PATH="$NODE_BIN_DIR:$PATH" node -v
PATH="$NODE_BIN_DIR:$PATH" npm -v
