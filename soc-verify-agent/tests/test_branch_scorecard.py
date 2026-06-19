from __future__ import annotations

import json
import uuid
from pathlib import Path

from soc_verify.branch_scorecard import build_all_branch_scorecards, write_branch_scorecard
from soc_verify.child_graph import validate_all_child_graphs
from soc_verify.execution_log import append_execution_log, load_execution_log


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_execution_log_append(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    append_execution_log(run_dir, command=["python", "ops.py"], node="run_gate", exit_code=0)
    logs = load_execution_log(run_dir)
    assert len(logs) == 1
    assert "python" in logs[0]["command"]


def test_branch_scorecard_from_trace(tmp_path: Path):
    project_dir = tmp_path / "PROJ"
    run_dir = project_dir / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "graph_trace.jsonl").write_text(
        '{"node":"setup"}\n{"node":"load_context"}\n{"node":"run_gate"}\n{"node":"evaluate"}\n',
        encoding="utf-8",
    )
    (run_dir / "md_only_prompt.md").write_text("x", encoding="utf-8")
    (run_dir / "graph_step.json").write_text("{}", encoding="utf-8")
    (run_dir / "verdict_g.json").write_text(
        json.dumps({"status": "PASS", "gate": "g"}),
        encoding="utf-8",
    )

    state = {
        "run_id": "r1",
        "project_id": "PROJ",
        "project_dir": str(project_dir),
        "stage": "sim",
        "group": "g",
        "verdict": "PASS",
        "trust_score": 0.8,
        "completeness": 0.9,
        "events": {"gates_run": 1, "env_fail_steps": 0, "info_interrupts": 0},
        "as_of": "2026-06-15",
    }
    child = validate_all_child_graphs(ROOT, "verify_group", state=state, run_dir=run_dir)
    payload = build_all_branch_scorecards(
        ROOT, project_dir, run_dir, state, child_summary=child
    )
    write_branch_scorecard(run_dir, payload)
    assert payload["branch_count"] >= 3
    assert (run_dir / "branch_scorecard.json").is_file()
    card = payload["branches"][0]
    assert "failure_beci" in card
    assert "C" in card["failure_beci"]
    assert "B" in card["failure_beci"]