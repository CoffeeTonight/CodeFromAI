#!/bin/bash
# Legacy name — runs full engine install.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/install_engine.sh" "$@"