#!/usr/bin/env bash
# goal_build_id = 18 — freeze attempt patch via capture git (sole writer)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch}"
GOAL_ROOT="${SOCVERIF_GOAL_ROOT:-$(dirname "$SCRATCH")}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH"
cd "$ROOT"

export SOCVERIF_CFA_HARNESS="$ROOT"
export GROK_WORKSPACE_ROOT="$ROOT"
export SOCVERIF_GOAL_ROOT="$GOAL_ROOT"

bash scripts/freeze_classifier_snapshot.sh 2>&1 | tee "$SCRATCH/sync_classifier_evidence.log"

python3 -m socverif.classifier_anchor assert \
  --scratch "$SCRATCH" \
  --goal-root "$GOAL_ROOT" \
  --harness-root "$ROOT" \
  2>&1 | tee "$SCRATCH/validate_patch.log"

grep -q '"ok": true' "$SCRATCH/validate_patch.log"
echo "sync_classifier_evidence: frozen attempt patch" | tee "$SCRATCH/sync_classifier_count.log"