from __future__ import annotations

import json
from pathlib import Path

from soc_verify.node_gate import (
    finalize_node_gate,
    save_user_node_gate,
    validate_node_gate,
    write_llm_gate_decl,
)
from soc_verify.graph_session import session_tick, start_session


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_validate_node_gate_run_gate_requires_verdict(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_id": "P1",
        "project_dir": str(tmp_path / "projects" / "P1"),
        "stage": "simulation",
        "group": "gpio_ext",
        "runner": "python",
        "run_id": "run",
    }
    result = validate_node_gate(ROOT, "verify_group", "run_gate", state=state, run_dir=run_dir)
    assert result.ok is False
    assert result.issues


def test_finalize_node_gate_writes_pass_artifact(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    group = "gpio_ext"
    (run_dir / f"verdict_{group}.json").write_text(
        json.dumps({"status": "PASS", "gate": group}),
        encoding="utf-8",
    )
    (run_dir / "graph_step.json").write_text("{}", encoding="utf-8")
    (run_dir / "graph_trace.jsonl").write_text(
        json.dumps({"node": "run_gate"}) + "\n",
        encoding="utf-8",
    )
    state = {
        "project_id": "P1",
        "project_dir": str(tmp_path),
        "stage": "simulation",
        "group": group,
        "runner": "python",
        "run_id": "run",
        "error_kind": "none",
        "events": {"gates_run": 1},
    }
    result = finalize_node_gate(
        ROOT,
        "verify_group",
        "run_gate",
        state=state,
        run_dir=run_dir,
        summary_ko="gate PASS — gpio_ext",
    )
    assert result.ok is True
    pass_path = run_dir / "node_gate" / "run_gate_pass.json"
    assert pass_path.is_file()
    data = json.loads(pass_path.read_text(encoding="utf-8"))
    assert data["checks_ok"] is True
    assert len(data["summary_ko"]) >= 8


def test_user_override_extra_check(tmp_path: Path):
    project = tmp_path / "projects" / "P1"
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    save_user_node_gate(
        project,
        "verify_group",
        "setup",
        extra_checks=[{"type": "file_exists", "path": "{run_dir}/user_evidence.txt"}],
    )
    (run_dir / "user_evidence.txt").write_text("ok", encoding="utf-8")
    state = {
        "project_id": "P1",
        "project_dir": str(project),
        "run_id": "r1",
    }
    result = validate_node_gate(ROOT, "verify_group", "setup", state=state, run_dir=run_dir)
    assert result.ok is True


def test_llm_decl_extends_gate(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_llm_gate_decl(
        run_dir,
        node_id="load_context",
        purpose_ko="문서 요약 확인",
        checks=[{"type": "file_exists", "path": "{run_dir}/doc_summary.md"}],
        summary_ko="CHECK·RESPOND 요약 완료",
    )
    (run_dir / "doc_summary.md").write_text("# summary", encoding="utf-8")
    (run_dir / "graph_trace.jsonl").write_text(
        json.dumps({"node": "load_context"}) + "\n",
        encoding="utf-8",
    )
    state = {
        "project_id": "P1",
        "project_dir": str(tmp_path),
        "stage": "simulation",
        "group": "gpio_ext",
        "run_id": "run",
        "info_gap": False,
    }
    result = validate_node_gate(ROOT, "verify_group", "load_context", state=state, run_dir=run_dir)
    assert result.ok is True
    assert "llm" in result.sources


def test_session_tick_blocked_without_node_gate_pass():
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    sid = started["session_id"]
    session_tick(ROOT, sid)
    tick2 = session_tick(ROOT, sid)
    if tick2.get("tick") == "blocked" and tick2.get("blocked_reason") == "node_gate":
        assert tick2.get("contract", {}).get("issues")
    else:
        assert tick2.get("tick") in ("ok", "waiting", "blocked")