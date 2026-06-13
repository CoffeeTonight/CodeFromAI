#!/usr/bin/env bash
# VCS compile (-kdb) for Verdi hierarchy. Usage: ./scripts/vcs/compile.sh <view>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VCS="${VCS:-vcs}"
VIEW="${1:-full_campaign}"

if ! command -v "$VCS" >/dev/null 2>&1; then
  echo "[vcs] $VCS not in PATH" >&2; exit 1
fi

case "$VIEW" in
  rtl) TOP="${VERDI_TOP:-verif_vcpu_soc_cell}"; FLIST="filelists/work/verdi_rtl.f" ;;
  full_campaign) TOP="${VERDI_TOP:-tb_full_campaign}"; FLIST="filelists/test/verdi_full_campaign.f" ;;
  soc_manifest) TOP="${VERDI_TOP:-tb_soc_manifest}"; FLIST="filelists/test/verdi_soc_manifest.f" ;;
  *)
    echo "[vcs] unknown view: $VIEW" >&2
    echo "  views: rtl full_campaign soc_manifest" >&2
    exit 1 ;;
esac

OUTDIR="sim_build/vcs_${VIEW}"
[[ -f "$FLIST" ]] || { echo "[vcs] missing $FLIST — run: ./example.sh gen" >&2; exit 1; }

mkdir -p "$OUTDIR"
echo "[vcs] compile view=$VIEW top=$TOP → $OUTDIR/simv"
"$VCS" -sverilog -full64 -kdb -debug_access+all \
  -f "$FLIST" -top "$TOP" -o "$OUTDIR/simv" -Mdir="$OUTDIR/csrc"
echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir [-ssf <wave.fsdb>]"
