#!/usr/bin/env bash
# Open Test — internal regression (simple_soc + full_campaign) in Synopsys Verdi (source + optional VCD).
# Requires: ./example.sh gen  (generated .vh + filelists)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VERDI="${VERDI:-verdi}"
TOP="${VERDI_TOP:-tb_full_campaign}"
FLIST="filelists/test/verdi_full_campaign.f"
WAVE="${1:-}"

if ! command -v "$VERDI" >/dev/null 2>&1; then
  echo "[verdi] $VERDI not in PATH — set VERDI= or load Synopsys env (module load vcs)" >&2
  exit 1
fi
[[ -f "$FLIST" ]] || { echo "[verdi] missing $FLIST — run: ./example.sh gen" >&2; exit 1; }

ARGS=(-sv -nologo -f "$FLIST" -top "$TOP")
DEFAULT_VCD="sim_build/tb_full_campaign.vcd"
if [[ -z "$WAVE" && -f "$DEFAULT_VCD" ]]; then
  WAVE="$DEFAULT_VCD"
fi
if [[ -n "$WAVE" ]]; then
  if [[ -f "$WAVE" ]]; then
    ARGS+=(-ssf "$WAVE")
    echo "[verdi] waveform: $WAVE"
  else
    echo "[verdi] WARN waveform not found: $WAVE (source-only)" >&2
  fi
fi
echo "[verdi] $VERDI -top $TOP -f $FLIST ${ARGS[*]:3}"
exec "$VERDI" "${ARGS[@]}"
