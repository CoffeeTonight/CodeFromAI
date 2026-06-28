#!/usr/bin/env bash
# Shared VERIF-CPU-SOC script helpers (PROJECT_DIR, TAG, logging).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
TAG="${TAG:-main}"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}