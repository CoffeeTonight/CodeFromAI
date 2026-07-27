"""Training lap runner — one-shot verify_group with loop_metrics.json."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from soc_verify.graph_session import session_status, session_tick, start_session
from soc_verify.models import save_yaml
from soc_verify.run_profile import profile_requires_held_out

VALID_SCENARIOS = frozenset({"pass", "env_fail", "verif_fail"})
LOOP_METRICS_NAME = "loop_metrics.json"


def set_training_scenario(project_dir: Path, scenario: str) -> Path:
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"invalid scenario {scenario!r}; expected one of {sorted(VALID_SCENARIOS)}")
    path = project_dir / "meta" / "training_scenario.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    save_yaml(path, {"scenario": scenario})
    return path


def build_loop_metrics(
    *,
    root: Path,
    project_id: str,
    stage: str,
    group: str,
    profile: str,
    scenario: str,
    session_id: str,
    status: dict[str, Any],
    tick_count: int,
    elapsed_s: float,
    blocked_reason: str = "",
) -> dict[str, Any]:
    state = status.get("state") or {}
    run_id = str(state.get("run_id") or "")
    run_dir = root / "projects" / project_id / "runs" / run_id if run_id else None
    weakness_count = 0
    if run_dir and (run_dir / "weakness_report.json").is_file():
        try:
            wr = json.loads((run_dir / "weakness_report.json").read_text(encoding="utf-8"))
            weakness_count = len(wr.get("weaknesses") or [])
        except json.JSONDecodeError:
            weakness_count = 0

    return {
        "contract": "loop_metrics_v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root.resolve()),
        "project_id": project_id,
        "stage": stage,
        "group": group,
        "profile": profile,
        "scenario": scenario,
        "session_id": session_id,
        "run_id": run_id,
        "finished": bool(status.get("finished")),
        "verdict": state.get("verdict"),
        "tick_count": tick_count,
        "elapsed_s": round(elapsed_s, 3),
        "blocked_reason": blocked_reason or None,
        "last_completed_node": status.get("last_completed_node"),
        "weakness_count": weakness_count,
        "run_profile": state.get("run_profile"),
        "require_held_out": profile_requires_held_out(root, profile),
    }


def write_loop_metrics(run_dir: Path, metrics: dict[str, Any]) -> Path:
    path = run_dir / LOOP_METRICS_NAME
    path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run_training_lap(
    root: Path,
    *,
    project_id: str,
    stage: str,
    group: str,
    profile: str = "training",
    scenario: str = "pass",
    max_ticks: int = 30,
) -> dict[str, Any]:
    """Start verify_group session, drive to END, emit loop_metrics.json."""
    root = root.resolve()
    project_dir = root / "projects" / project_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"project not found: {project_dir}")

    set_training_scenario(project_dir, scenario)
    t0 = time.monotonic()
    started = start_session(
        root,
        graph_id="verify_group",
        project_id=project_id,
        stage=stage,
        group=group,
        run_profile=profile,
    )
    session_id = started["session_id"]
    tick_count = 0
    blocked_reason = ""

    for _ in range(max_ticks):
        st = session_status(root, session_id)
        if st.get("finished"):
            break
        tick = session_tick(root, session_id, auto_invoke_llm=False)
        tick_count += 1
        if tick.get("tick") in ("blocked", "waiting"):
            blocked_reason = str(tick.get("blocked_reason") or tick.get("tick"))
            break

    final_status = session_status(root, session_id)
    elapsed_s = time.monotonic() - t0
    metrics = build_loop_metrics(
        root=root,
        project_id=project_id,
        stage=stage,
        group=group,
        profile=profile,
        scenario=scenario,
        session_id=session_id,
        status=final_status,
        tick_count=tick_count,
        elapsed_s=elapsed_s,
        blocked_reason=blocked_reason,
    )

    run_id = metrics.get("run_id")
    metrics_path = None
    if run_id:
        run_dir = project_dir / "runs" / run_id
        if run_dir.is_dir():
            metrics_path = write_loop_metrics(run_dir, metrics)

    return {
        "ok": final_status.get("finished") and not blocked_reason,
        "session_id": session_id,
        "loop_metrics": metrics,
        "loop_metrics_path": str(metrics_path) if metrics_path else None,
        "status": final_status,
    }