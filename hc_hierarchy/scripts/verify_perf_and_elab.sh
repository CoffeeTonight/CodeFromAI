#!/usr/bin/env bash
# Regression + perf meta check with full log under logs/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="${ROOT}/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/verify_${STAMP}.log"
mkdir -p "$LOG_DIR"

exec > >(tee -a "$LOG") 2>&1
echo "=== verify_perf_and_elab ==="
echo "log=$LOG"
echo "started=$(date -u -Iseconds)"

FAIL=0
run() {
  echo ""
  echo "--- $* ---"
  if "$@"; then
    echo "OK: $*"
  else
    echo "FAIL: $* (exit $?)"
    FAIL=1
  fi
}

run python3 -c "from hch.engine.availability import check_engine; s=check_engine(); print(s); assert s.available"

run pytest tests/phase26/test_perf_filelist_cache.py -q --tb=long
run pytest tests/phase26/test_elab_source_prune.py -q --tb=long
run pytest tests/phase22 tests/phase23 tests/phase24 tests/phase25 tests/phase26 -q -m "not slow" --tb=line

echo ""
echo "--- bench: fast elab index ---"
run python3 <<'PY'
import json, time
from pathlib import Path
from hch.index.loader import build_index_from_filelist

fl = "design/synthetic_deep_rtl/top_deep_soc.hc.f"
db = f"/tmp/hch_verify_{int(time.time())}.hch.db"
t0 = time.perf_counter()
store = build_index_from_filelist(
    fl, db, top_module="deep_soc_top", elaborate=True, elab_fast=True
)
elapsed = time.perf_counter() - t0
row = {
    "elapsed_s": round(elapsed, 2),
    "ingest_mode": store.get_meta("ingest_mode"),
    "tier_e_single_pass": store.get_meta("tier_e_single_pass"),
    "ingest_source_count": store.get_meta("ingest_source_count"),
    "elab_succeeded": store.get_meta("elab_succeeded"),
    "instances": store.count_instances(),
}
print(json.dumps(row, indent=2))
store.close()
Path(db).unlink(missing_ok=True)
assert row["ingest_mode"] == "fast", row
assert row["elab_succeeded"] == "1", row
assert int(row["instances"]) == 8, row
assert row["tier_e_single_pass"] == "1", row
PY

echo ""
echo "finished=$(date -u -Iseconds) overall_fail=$FAIL"
echo "log=$LOG"
exit "$FAIL"