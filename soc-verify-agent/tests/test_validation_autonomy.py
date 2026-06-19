from __future__ import annotations

import json
from pathlib import Path

from soc_verify.validation_autonomy import (
    _mechanical_judgment,
    apply_validation_judgment,
    collect_validation_items,
    filter_work_queue_by_validation,
    load_validation_judgment,
    load_validation_state,
    run_pending_repro,
    save_validation_state,
)


def test_mechanical_judgment_retry_gate_on_failures():
    j = _mechanical_judgment(
        {
            "stage": "sim",
            "group": "g",
            "items": [{"item_id": "t1", "status": "fail"}],
        }
    )
    assert j["sequence_action"] == "retry_gate"


ROOT = Path(__file__).resolve().parents[1]


def test_collect_validation_items_from_checklist_log(tmp_path: Path):
    project = tmp_path / "projects" / "TEST-SOC"
    stage, group = "simulation", "gpio_ext"
    (project / "verification" / stage / group).mkdir(parents=True)
    (project / "verification" / stage / group / "CHECK.md").write_text(
        """
## PASS 조건
| tier | 마커 |
|------|------|
| `sim_single` | PASS marker |
| `sim_burst` | burst OK |
""",
        encoding="utf-8",
    )
    run_dir = project / "runs" / "run001"
    run_dir.mkdir(parents=True)
    (run_dir / "gpio_ext.log").write_text(
        "sim_burst running\nChecklist: 10 passed / 2 failed\n[ERROR] burst timeout\n",
        encoding="utf-8",
    )
    (run_dir / "verdict_gpio_ext.json").write_text(
        json.dumps({"status": "FAIL"}),
        encoding="utf-8",
    )

    payload = collect_validation_items(project, stage=stage, group=group, run_dir=run_dir)
    assert payload["contract"] == "validation_items_v1"
    assert payload["needs_judgment"] is True
    assert payload["failing_count"] >= 1


def test_apply_validation_judgment_exclude_and_narrow(tmp_path: Path):
    project = tmp_path / "projects" / "TEST-SOC"
    run_dir = project / "runs" / "run002"
    run_dir.mkdir(parents=True)
    judgment = {
        "contract": "validation_judgment_v1",
        "verdict_summary_ko": "sim_cpu_sync 실패",
        "sequence_action": "continue_remaining",
        "items": [
            {
                "item_id": "sim_cpu_sync",
                "status": "fail",
                "action": "exclude",
                "user_summary_ko": "known issue TRACK-1",
                "exclude_reason": "TRACK-1",
            },
            {
                "item_id": "sim_burst",
                "status": "fail",
                "action": "narrow_cause",
                "user_summary_ko": "burst timeout",
                "narrow_hints": ["slave_rw.log"],
            },
        ],
    }
    result = apply_validation_judgment(
        project,
        run_dir,
        judgment,
        stage="simulation",
        group="slave_rw",
    )
    assert result["ok"] is True
    assert (run_dir / "validation_narrow.md").is_file()
    state = load_validation_state(project)
    assert len(state["excluded_items"]) == 1
    assert state["last_sequence_action"] == "continue_remaining"
    assert "pending_repro" in state


def test_run_pending_repro_executes_item_script(tmp_path: Path):
    project = tmp_path / "projects" / "P1"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "repro_sim_burst.sh").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    run_dir = project / "runs" / "run_repro"
    run_dir.mkdir(parents=True)
    save_validation_state(
        project,
        {
            "pending_repro": [
                {
                    "item_id": "sim_burst",
                    "stage": "simulation",
                    "group": "slave_rw",
                    "script": "scripts/repro_sim_burst.sh",
                    "run_id": "run_repro",
                }
            ],
        },
    )
    result = run_pending_repro(
        project,
        run_dir,
        stage="simulation",
        group="slave_rw",
        run_id="run_repro",
    )
    assert result["executed_count"] == 1
    assert result["results"][0]["status"] == "pass"
    assert (run_dir / "validation_repro_results.json").is_file()


def test_run_pending_repro_no_pending_writes_empty_results(tmp_path: Path):
    project = tmp_path / "projects" / "P2"
    run_dir = project / "runs" / "run_empty"
    run_dir.mkdir(parents=True)
    result = run_pending_repro(
        project,
        run_dir,
        stage="simulation",
        group="gpio_ext",
        run_id="run_empty",
    )
    assert result["pending_count"] == 0
    assert result["results"] == []
    assert (run_dir / "validation_repro_results.json").is_file()


def test_load_validation_judgment_resolves_repo_root_for_mechanical_fallback(tmp_path: Path):
    """run_dir = root/projects/P/runs/R — mechanical_fallback must read root/registry spec."""
    root = tmp_path
    (root / "registry").mkdir()
    (root / "registry" / "validation_autonomy_spec.yaml").write_text(
        "mechanical_fallback:\n  sequence_action: halt\n",
        encoding="utf-8",
    )
    project = root / "projects" / "P1"
    run_dir = project / "runs" / "run003"
    run_dir.mkdir(parents=True)
    items = {
        "stage": "sim",
        "group": "g",
        "items": [{"item_id": "t1", "status": "fail"}],
    }
    j = load_validation_judgment(run_dir, items)
    assert j["sequence_action"] == "halt"
    assert j["source"] == "mechanical"


def test_filter_work_queue_skips_excluded_gate(tmp_path: Path):
    root = tmp_path
    project = root / "projects" / "P1"
    project.mkdir(parents=True)
    save_validation_state(
        project,
        {
            "excluded_items": [
                {"item_id": "", "stage": "static", "group": "coi_conn", "reason": "waived"},
            ],
        },
    )
    queue = [
        {"kind": "verify", "project_id": "P1", "stage": "static", "group": "coi_conn"},
        {"kind": "verify", "project_id": "P1", "stage": "simulation", "group": "slave_rw"},
    ]
    filtered = filter_work_queue_by_validation(root, queue)
    assert len(filtered) == 1
    assert filtered[0]["group"] == "slave_rw"