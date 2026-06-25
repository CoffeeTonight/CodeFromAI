#!/usr/bin/env bash
# Synopsys VCS — compile (if needed) + run simv.
# Usage: ./scripts/vcs/run.sh [view]
# Env: FORCE_COMPILE=1  VCS_VCD=<path>  VCS_SIMV_OPTS="+ntb_random_seed=1"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib/eda_lists.sh
source "$ROOT/scripts/lib/eda_lists.sh"

VIEW="${1:-full_campaign}"
eda_require_view "$VIEW"
OUTDIR="sim_build/vcs_${VIEW}"
SIMV="$OUTDIR/simv"

if [[ ! -x "$SIMV" || "${FORCE_COMPILE:-0}" == "1" ]]; then
  echo "[vcs] compile view=$VIEW"
  "$ROOT/scripts/vcs/compile.sh" "$VIEW"
fi

VCD="${VCS_VCD:-$OUTDIR/sim.vcd}"
mkdir -p "$OUTDIR"
echo "[vcs] run $SIMV +vcd+$VCD"
"$SIMV" +vcd+:"$VCD" ${VCS_SIMV_OPTS:-} | tee "$OUTDIR/sim.log"
echo "[vcs] log=$OUTDIR/sim.log vcd=$VCD"
echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir -ssf $VCD"
