#!/usr/bin/env bash
# Self-Harness CLI — mine / propose / propose-llm / validate / held-out / meta-collect / status / context
set -euo pipefail
source "$(dirname "$0")/_common.sh"
export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
ROOT="$(cd "$PROJECT_DIR/../.." && pwd)"

usage() {
  cat <<EOF
Usage: $0 <cmd> PROJECT [RUN_ID] [options]

  mine PROJECT RUN_ID [--propose]       Mine weaknesses; optional harness proposal
  propose PROJECT RUN_ID                Generate harness_proposal.json
  propose-llm PROJECT RUN_ID            Generate harness_proposal_llm.json
  validate PROJECT RUN_ID               Run pytest validation gate
  held-out PROJECT RUN_ID               Run held-out reverify before promote
  meta-collect PROJECT RUN_ID           Full mine+propose+ERL+llm_brief pipeline
  status PROJECT RUN_ID                 Artifact status
  context PROJECT [--stage S] [--group G] [--error-kind K] [--limit N]

Env: SOC_VERIFY_WORK_ROOT (default ~/tools/soc-verify-agent-work); root is __CFA/soc-verify-agent
EOF
}

cmd="${1:-}"
shift || { usage; exit 1; }

case "$cmd" in
  mine|propose|propose-llm|validate|held-out|status|meta-collect)
    project="${1:-}"; run_id="${2:-}"
    [[ -n "$project" && -n "$run_id" ]] || { usage; exit 2; }
    shift 2 || true
    propose=""
    while (( $# > 0 )); do
      case "$1" in
        --propose) propose="--propose" ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
      shift
    done
    python3 - "$ROOT" "$cmd" "$project" "$run_id" "$propose" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
cmd, project, run_id = sys.argv[2:5]
propose = "--propose" in sys.argv[5:]
project_dir = root / "projects" / project
run_dir = project_dir / "runs" / run_id
if not project_dir.is_dir() or not run_dir.is_dir():
    print(json.dumps({"error": "project or run not found"}, indent=2))
    raise SystemExit(2)
from ops.self_harness import (
    harness_status, load_weakness_report, mine_weaknesses,
    propose_harness_edits, propose_llm_skill_patches, retrieve_erl_context,
    validate_harness_proposal, held_out_reverify, write_weakness_report,
)
from ops.erl_reflect import write_erl_heuristic
from ops.meta_collect import run_meta_collect

if cmd == "mine":
    report = mine_weaknesses(root, project_dir, run_dir)
    write_weakness_report(run_dir, report)
    if propose:
        propose_harness_edits(root, project_dir, run_dir, weakness_report=report)
    sig_path = run_dir / "improvement_signal.json"
    signals = {}
    if sig_path.is_file():
        signals = json.loads(sig_path.read_text(encoding="utf-8"))
    write_erl_heuristic(project_dir, run_dir, signals=signals, weakness_report=report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
elif cmd == "propose":
    payload = propose_harness_edits(root, project_dir, run_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
elif cmd == "propose-llm":
    payload = propose_llm_skill_patches(root, project_dir, run_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
elif cmd == "validate":
    result = validate_harness_proposal(root, run_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result.get("ok") else 1)
elif cmd == "held-out":
    result = held_out_reverify(root, run_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result.get("ok") else 1)
elif cmd == "meta-collect":
    result = run_meta_collect(root, project_dir, run_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print(json.dumps(harness_status(project_dir, run_dir), indent=2, ensure_ascii=False))
PY
    ;;
  context)
    project="${1:-}"
    [[ -n "$project" ]] || { usage; exit 2; }
    shift || true
    stage="" group="" error_kind="" limit=5
    while (( $# > 0 )); do
      case "$1" in
        --stage) stage="${2:-}"; shift 2 ;;
        --group) group="${2:-}"; shift 2 ;;
        --error-kind) error_kind="${2:-}"; shift 2 ;;
        --limit) limit="${2:-5}"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done
    python3 - "$ROOT" "$project" "$stage" "$group" "$error_kind" "$limit" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
project_dir = root / "projects" / sys.argv[2]
from ops.self_harness import retrieve_erl_context
ctx = retrieve_erl_context(
    project_dir,
    stage=sys.argv[3],
    group=sys.argv[4],
    error_kind=sys.argv[5],
    limit=int(sys.argv[6]),
)
print(json.dumps({"heuristics": ctx, "count": len(ctx)}, indent=2, ensure_ascii=False))
PY
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac