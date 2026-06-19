"""verify_group E2E — 10 consecutive successes to END (stub LLM, EXAMPLE-SOC)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soc_verify.graph_session import session_status, session_tick, start_session

ROOT = Path(__file__).resolve().parents[1]
MAX_TICKS = 25
RUNS = 10


def _run_verify_group_to_end() -> dict:
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    sid = started["session_id"]
    log: list[dict] = []
    last: dict = {}

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
            last["finished"] = True
            last["session_id"] = sid
            last["log"] = log
            last["verdict"] = (st.get("state") or {}).get("verdict")
            last["nodes"] = [
                e["completed"]
                for e in log
                if e.get("completed")
            ]
            return last

    st = session_status(ROOT, sid)
    last["finished"] = st.get("finished")
    last["session_id"] = sid
    last["log"] = log
    last["verdict"] = (st.get("state") or {}).get("verdict")
    return last


@pytest.mark.parametrize("run_index", range(RUNS))
def test_verify_group_e2e_success(run_index: int) -> None:
    result = _run_verify_group_to_end()
    assert result.get("tick") != "blocked", (
        f"run {run_index + 1} blocked: {result.get('blocked_reason')} "
        f"log={json.dumps(result.get('log', []), ensure_ascii=False)}"
    )
    assert result.get("finished") is True, (
        f"run {run_index + 1} not finished: log={json.dumps(result.get('log', []), ensure_ascii=False)}"
    )
    assert result.get("verdict") == "PASS", f"run {run_index + 1} verdict={result.get('verdict')}"
    nodes = result.get("nodes") or []
    assert "meta_queue" in nodes, f"run {run_index + 1} nodes={nodes}"
    assert len(nodes) >= 11, f"run {run_index + 1} only {len(nodes)} nodes"


def test_verify_group_e2e_success_auto_invoke_llm() -> None:
    """Single run with auto_invoke_llm — entry gate must not require exit artifacts."""
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    sid = started["session_id"]
    for _ in range(MAX_TICKS):
        last = session_tick(ROOT, sid, auto_invoke_llm=True)
        if last.get("tick") == "blocked":
            pytest.fail(f"blocked at {last.get('blocked_reason')}: {last.get('contract')}")
        if session_status(ROOT, sid).get("finished"):
            assert last.get("verdict") == "PASS" or (session_status(ROOT, sid).get("state") or {}).get("verdict") == "PASS"
            return
    pytest.fail("did not finish within max ticks")