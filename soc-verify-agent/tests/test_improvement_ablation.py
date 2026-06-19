from __future__ import annotations

import json
from pathlib import Path

from soc_verify.improvement_ablation import build_ablation_record, write_ablation
from soc_verify.improvement_eval import append_history, build_snapshot


def test_ablation_links_proposal_delta(tmp_path: Path):
    project = tmp_path / "PROJ"
    run_dir = project / "runs" / "r2"
    run_dir.mkdir(parents=True)
    (project / "meta_proposals").mkdir(parents=True)
    (project / "meta_proposals" / "r1.json").write_text(
        json.dumps(
            {
                "run_id": "r1",
                "status": "queued",
                "proposal": {
                    "run_id": "r1",
                    "summary": "fix ops",
                    "changes": [{"layer": "ops", "target": "ops/s/g.py", "rationale": "parity"}],
                },
            }
        ),
        encoding="utf-8",
    )

    signals_fail = {
        "run_id": "r1",
        "project_id": "PROJ",
        "stage": "sim",
        "group": "g",
        "verdict": "FAIL",
        "completeness": 0.5,
        "trust_score": 0.5,
        "runner": "python",
        "runner_mode": "python",
        "fix_round": 0,
        "codegen_round": 0,
        "bridge_round": 0,
        "error_kind": "none",
        "parity_ok": False,
        "llm_node_count": 0,
        "graph_step_count": 0,
        "stalemate": False,
        "promoted": False,
        "llm_fix_rounds": 0,
        "tool_incidents": 0,
        "env_fail_steps": 0,
    }
    append_history(project, build_snapshot(project, run_dir, signals_fail, as_of="2026-06-14"))

    signals_pass = dict(signals_fail)
    signals_pass.update({"verdict": "PASS", "completeness": 0.9, "trust_score": 0.85, "parity_ok": True})
    snap = build_snapshot(project, run_dir, signals_pass, as_of="2026-06-15")

    rec = build_ablation_record(
        project,
        run_dir,
        run_id="r2",
        stage="sim",
        group="g",
        snapshot=snap.to_dict(),
        branch_scorecard={"branches": [{"success_rate": 1.0}]},
    )
    write_ablation(run_dir, rec)
    assert rec.get("linked_proposal") is not None
    assert (run_dir / "improvement_ablation.json").is_file()