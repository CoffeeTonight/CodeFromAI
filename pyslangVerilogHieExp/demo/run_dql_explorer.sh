#!/bin/bash
# One-command launcher for the DQL Explorer (Python Lark engine)
# Usage: ./demo/run_dql_explorer.sh

set -e

cd "$(dirname "$0")/.."

echo "=== DQL Explorer (Python Lark - aiming for JS HTML parity) ==="
echo ""
echo "Starting server on http://localhost:8765"
echo "Press Ctrl+C to stop."
echo ""

python3 demo/dql_explorer_server.py