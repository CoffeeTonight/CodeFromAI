# shellcheck shell=bash
# Shared paths for VERIF-CPU-SOC verification reproduction.
# Source from other scripts:  source "$(dirname "$0")/_common.sh"

set -euo pipefail

# Project root = parent of scripts/
if [[ -z "${PROJECT_DIR:-}" ]]; then
  _COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PROJECT_DIR="$(cd "${_COMMON_DIR}/.." && pwd)"
fi

# soc-verify-agent repo root (parent of projects/)
SOC_VERIFY_ROOT="$(cd "${PROJECT_DIR}/../.." && pwd)"

export PROJECT_DIR SOC_VERIFY_ROOT

# Tag from cache.yaml (fallback: main)
if [[ -z "${TAG:-}" ]]; then
  TAG="$(python3 -c "
import yaml
from pathlib import Path
p = Path('${PROJECT_DIR}') / 'cache.yaml'
try:
    d = yaml.safe_load(p.read_text()) or {}
    print((d.get('tag') or {}).get('value') or 'main')
except Exception:
    print('main')
" 2>/dev/null || echo main)"
fi
export TAG

# Run output directory
RUN_ID="${RUN_ID:-reproduce-${TAG}-$(date +%Y%m%d-%H%M%S)}"
RUN_DIR="${PROJECT_DIR}/runs/${RUN_ID}"
export RUN_ID RUN_DIR

log() { printf '[verify] %s\n' "$*"; }
die() { printf '[verify] ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

run_gate() {
  local name="$1"
  shift
  log "=== ${name} ==="
  log "cmd: $*"
  "$@"
  local ec=$?
  if [[ $ec -ne 0 ]]; then
    die "${name} failed (exit=${ec})"
  fi
  log "=== ${name} OK ==="
}