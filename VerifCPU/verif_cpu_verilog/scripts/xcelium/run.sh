#!/usr/bin/env bash
# Cadence Xcelium xrun — elaborate + simulate (single invocation).
# Usage: ./scripts/xcelium/run.sh [view]
# Env: XRUN_OPTS="-svseed random"  XRUN_PROBE=1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib/eda_lists.sh
source "$ROOT/scripts/lib/eda_lists.sh"

VIEW="${1:-full_campaign}"
XRUN="${XRUN:-xrun}"

eda_require_view "$VIEW"
TOP="${XRUN_TOP:-$(eda_top "$VIEW")}"
MANIFEST="$(eda_prefix "$VIEW")/manifest.list"
OUTDIR="sim_build/xcelium_${VIEW}"
mkdir -p "$OUTDIR"

if ! command -v "$XRUN" >/dev/null 2>&1; then
  echo "[xrun] $XRUN not in PATH — load Cadence env" >&2; exit 1
fi

PROBE_TCL=""
if [[ "${XRUN_PROBE:-1}" == "1" ]]; then
  PROBE_TCL="-input @probe.tcl"
  cat > "$OUTDIR/probe.tcl" <<EOF
database -open waves -shm -default
probe -create -all -depth all
run
exit
EOF
fi

echo "[xrun] view=$VIEW top=$TOP → $OUTDIR/xcelium.d"
XRUN_EXTRA=()
if [[ -n "${XRUN_OPTS:-}" ]]; then
  read -r -a XRUN_EXTRA <<< "$XRUN_OPTS"
fi
"$XRUN" -64bit -sv -timescale 1ns/1ps \
  -F "$MANIFEST" -top "$TOP" \
  -access +rwc -status \
  -xmlibdirname "$OUTDIR/xcelium.d" \
  -clean ${PROBE_TCL} "${XRUN_EXTRA[@]}"
echo "[xrun] waves: ${OUTDIR}/xcelium.d/shm"
echo "[xrun] SimVision: simvision -csdf ${OUTDIR}/xcelium.d"
