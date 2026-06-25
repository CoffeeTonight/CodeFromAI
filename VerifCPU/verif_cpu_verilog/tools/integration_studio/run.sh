#!/usr/bin/env bash
# Launch Integration Studio web UI (workspace = verif_cpu_verilog)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RTL_ROOT="$(cd "$ROOT/../.." && pwd)"
export PYTHONPATH="${RTL_ROOT}:${ROOT}:${PYTHONPATH:-}"

PORT=8765
REPLACE=0
EXTRA=()
while (( $# > 0 )); do
  case "$1" in
    --port)
      PORT="${2:?}"
      shift 2
      ;;
    --replace)
      REPLACE=1
      shift
      ;;
    *)
      EXTRA+=("$1")
      shift
      ;;
  esac
done

studio_health() {
  curl -sf -m 2 "http://127.0.0.1:${1}/api/config" >/dev/null 2>&1
}

stop_studio() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
  local pid
  for pid in $(pgrep -f "python3.*${ROOT}/server.py" 2>/dev/null || true); do
    [[ -z "$pid" || "$pid" == "$$" ]] && continue
    kill "$pid" 2>/dev/null || true
  done
  sleep 0.5
}

if (( REPLACE )); then
  stop_studio "$PORT"
elif studio_health "$PORT"; then
  echo "Integration Studio already running: http://127.0.0.1:${PORT}"
  exit 0
elif command -v fuser >/dev/null 2>&1 && fuser "${PORT}/tcp" >/dev/null 2>&1; then
  echo "[run.sh] port ${PORT} in use but not responding — retry with: $0 --replace" >&2
  exit 1
fi

exec python3 "$ROOT/server.py" --port "$PORT" "${EXTRA[@]}"