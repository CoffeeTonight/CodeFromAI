"""Training profile E2E — finalize → END, skip meta tail."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from soc_verify.graph_session import session_status, session_tick, start_session

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[1]
MAX_TICKS = 20
MAX_SECONDS = 120


def _run_training_to_end() -> dict:
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
        run_profile="training",
    )
    sid = started["session_id"]
    log: list[dict] = []
    t0 = time.monotonic()

    for tick_n in range(1, MAX_TICKS + 1):
        last = session_tick(ROOT, sid, auto_invoke_llm=False)
        log.append(
            {
                "tick": tick_n,
                "status": last.get("tick"),
                "completed": last.get("completed_node"),
                "blocked_reason": last.get("blocked_reason"),
            }
        )
        if last.get("tick") == "blocked":
            break
        st = session_status(ROOT, sid)
        if st.get("finished"):
            elapsed = time.monotonic() - t0
            nodes = [e["completed"] for e in log if e.get("completed")]
            state = st.get("state") or {}
            return {
                "finished": True,
                "session_id": sid,
                "log": log,
                "verdict": state.get("verdict"),
                "run_profile": state.get("run_profile"),
                "run_id": state.get("run_id"),
                "nodes": nodes,
                "tick_count": tick_n,
                "elapsed_s": elapsed,
            }

    st = session_status(ROOT, sid)
    return {
        "finished": st.get("finished"),
        "session_id": sid,
        "log": log,
        "verdict": (st.get("state") or {}).get("verdict"),
        "nodes": [e["completed"] for e in log if e.get("completed")],
        "tick_count": len(log),
        "elapsed_s": time.monotonic() - t0,
    }


def test_training_profile_skips_meta_tail():
    result = _run_training_to_end()
    blocked = [e for e in result.get("log", []) if e.get("status") == "blocked"]
    assert not blocked, f"blocked: {json.dumps(blocked, ensure_ascii=False)}"
    assert result.get("finished") is True, f"not finished: {json.dumps(result.get('log', []), ensure_ascii=False)}"
    assert result.get("verdict") == "PASS"
    assert result.get("run_profile") == "training"
    nodes = result.get("nodes") or []
    assert "finalize" in nodes
    assert "meta_queue" not in nodes
    assert "meta_collect" not in nodes
    run_id = result.get("run_id")
    assert run_id, "missing run_id in session state"
    weakness_path = ROOT / "projects" / "EXAMPLE-SOC" / "runs" / run_id / "weakness_report.json"
    assert weakness_path.is_file(), "training finalize must write weakness_report"
    # Training skips 4 meta nodes; EXAMPLE improvement loop still adds select/run/eval cycles.
    assert result.get("tick_count", 99) <= 16, f"too many ticks: {result.get('tick_count')}"
    assert result.get("elapsed_s", 999) < MAX_SECONDS, f"too slow: {result.get('elapsed_s'):.1f}s"