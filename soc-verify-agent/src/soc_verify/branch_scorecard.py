"""Per-branch scorecards — trust, success rate, C-I-E-B, retries, feedback (paper-grade)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from soc_verify.execution_log import load_execution_log
from soc_verify.improvement_eval import load_history
from soc_verify.models import load_yaml, save_yaml


SCORECARD_NAME = "branch_scorecard.json"
PROJECT_HISTORY = "scorecards/history.yaml"
WEEKLY_RETRIES = "scorecards/weekly_retries.yaml"


def _iso_week(d: str) -> str:
    try:
        dt = date.fromisoformat(d[:10])
    except ValueError:
        dt = date.today()
    return f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"


def _parse_trace_branches(run_dir: Path) -> list[dict[str, str]]:
    """Derive conditional edges visited from graph_trace.jsonl."""
    path = run_dir / "graph_trace.jsonl"
    if not path.is_file():
        return []
    nodes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            n = str(json.loads(line).get("node", ""))
            if n:
                nodes.append(n)
        except json.JSONDecodeError:
            continue

    branches: list[dict[str, str]] = []
    for i in range(len(nodes) - 1):
        branches.append({"from_node": nodes[i], "to_node": nodes[i + 1], "branch_id": f"{nodes[i]}->{nodes[i + 1]}"})
    return branches


def _failure_beci(state: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    gates = max(1, int(events.get("gates_run", 1)))
    completeness = float(state.get("completeness", 0.0))
    return {
        "C": {
            "completeness": completeness,
            "score": completeness,
            "note": "completeness (1-e)(1-t)(1-i)(1-l)",
        },
        "I": {
            "info_interrupts": int(events.get("info_interrupts", 0)),
            "info_gap": bool(state.get("info_gap")),
            "error_kind_info": state.get("error_kind") == "info",
            "rate": int(events.get("info_interrupts", 0)) / gates,
        },
        "E": {
            "env_fail_steps": int(events.get("env_fail_steps", 0)),
            "error_kind_env": state.get("error_kind") == "env",
            "rate": int(events.get("env_fail_steps", 0)) / gates,
        },
        "B": {
            "bridge_round": int(state.get("bridge_round", 0)),
            "bridge_applied": bool((state.get("bridge_outcome") or {}).get("applied")),
            "error_kind_tool": state.get("error_kind") == "tool",
            "rate": int(state.get("bridge_round", 0)) / max(1, int(state.get("fix_round", 0)) + 1),
        },
    }


def _collect_feedback(project_dir: Path, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    questions = list(state.get("questions") or [])
    qpath = project_dir / "questions_pending.md"
    pending_excerpt = ""
    if qpath.is_file():
        pending_excerpt = qpath.read_text(encoding="utf-8")[-800:]

    feedback_improvement: list[dict[str, Any]] = []
    meta_dir = project_dir / "meta_proposals"
    if meta_dir.is_dir():
        for p in sorted(meta_dir.glob("*.json"))[-5:]:
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                feedback_improvement.append(
                    {
                        "run_id": rec.get("run_id"),
                        "status": rec.get("status"),
                        "queued_at": rec.get("queued_at"),
                    }
                )
            except json.JSONDecodeError:
                continue

    sub_stop = run_dir / "sub_stop.json"
    sub = {}
    if sub_stop.is_file():
        try:
            sub = json.loads(sub_stop.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sub = {}

    return {
        "questions": questions,
        "questions_pending_excerpt": pending_excerpt,
        "sub_stop": sub,
        "feedback_improvement_history": feedback_improvement,
    }


def _weekly_retries(project_dir: Path, stage: str, group: str, *, as_of: str) -> dict[str, Any]:
    history = load_history(project_dir, stage, group)
    week = _iso_week(as_of)
    retries = 0
    reasons: list[str] = []
    for entry in history:
        if _iso_week(str(entry.get("as_of", ""))) != week:
            continue
        if entry.get("verdict") != "PASS":
            retries += 1
            reasons.append(str(entry.get("error_kind") or entry.get("verdict")))
        elif int(entry.get("fix_round", 0)) > 0:
            retries += 1
            reasons.append("fix_round_retry")

    return {"iso_week": week, "retry_count": retries, "reasons": reasons[:20]}


def _append_weekly_aggregate(project_dir: Path, weekly: dict[str, Any], branch_id: str) -> None:
    path = project_dir / WEEKLY_RETRIES
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path)
    if not data:
        data = {"contract": "weekly_retries_v1", "weeks": {}}
    weeks = data.setdefault("weeks", {})
    key = weekly["iso_week"]
    bucket = weeks.setdefault(key, {"total_retries": 0, "branches": {}})
    bucket["total_retries"] = int(bucket.get("total_retries", 0)) + int(weekly.get("retry_count", 0))
    branches = bucket.setdefault("branches", {})
    branches[branch_id] = int(branches.get(branch_id, 0)) + int(weekly.get("retry_count", 0))
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)


def build_branch_scorecard(
    *,
    graph_id: str,
    branch: dict[str, str],
    state: dict[str, Any],
    run_dir: Path,
    project_dir: Path,
    child_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = dict(state.get("events") or {})
    from_node = branch["from_node"]
    to_node = branch["to_node"]
    branch_id = f"{graph_id}:{branch['branch_id']}"

    verdict = str(state.get("verdict", "UNKNOWN"))
    success = 1.0 if verdict == "PASS" and to_node not in ("finalize", "select_runner") else 0.0
    if from_node == "run_gate" and to_node == "evaluate":
        success = 1.0 if verdict == "PASS" else 0.0
    if from_node == "parity_check" and to_node == "promote":
        success = 1.0 if state.get("parity_ok") else 0.0

    retry_count = int(state.get("fix_round", 0)) + int(state.get("codegen_round", 0)) + int(
        state.get("bridge_round", 0)
    )

    backup_manifest = run_dir / "backup" / "manifest.json"
    backup = {}
    if backup_manifest.is_file():
        try:
            backup = json.loads(backup_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = {}

    as_of = str(state.get("as_of", date.today().isoformat()))
    weekly = _weekly_retries(project_dir, state.get("stage", ""), state.get("group", ""), as_of=as_of)
    feedback = _collect_feedback(project_dir, run_dir, state)

    return {
        "branch_id": branch_id,
        "parent_graph": graph_id,
        "from_node": from_node,
        "to_node": to_node,
        "trust_score": float(state.get("trust_score", 0.0)),
        "success_rate": success,
        "verdict": verdict,
        "failure_beci": _failure_beci(state, events),
        "retry_count": retry_count,
        "execution_commands": load_execution_log(run_dir),
        "backup_manifest": backup,
        "feedback": feedback,
        "weekly_retries": weekly,
        "child_graph_evidence": child_evidence or {},
        "as_of": as_of,
    }


def build_all_branch_scorecards(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    state: dict[str, Any],
    *,
    graph_id: str = "verify_group",
    child_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    branches = _parse_trace_branches(run_dir)
    if not branches:
        branches = [{"from_node": "setup", "to_node": "finalize", "branch_id": "setup->finalize"}]

    cards = [
        build_branch_scorecard(
            graph_id=graph_id,
            branch=b,
            state=state,
            run_dir=run_dir,
            project_dir=project_dir,
            child_evidence=child_summary,
        )
        for b in branches
    ]

    for card in cards:
        _append_weekly_aggregate(project_dir, card["weekly_retries"], card["branch_id"])

    payload = {
        "contract": "branch_scorecard_v1",
        "graph_id": graph_id,
        "run_id": state.get("run_id", run_dir.name),
        "project_id": state.get("project_id", project_dir.name),
        "stage": state.get("stage", ""),
        "group": state.get("group", ""),
        "branches": cards,
        "branch_count": len(cards),
    }
    return payload


def write_branch_scorecard(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / SCORECARD_NAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def append_project_scorecard_history(project_dir: Path, payload: dict[str, Any]) -> None:
    path = project_dir / PROJECT_HISTORY
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path)
    if not data:
        data = {"contract": "scorecard_history_v1", "runs": []}
    runs = list(data.get("runs") or [])
    runs.append(
        {
            "run_id": payload.get("run_id"),
            "as_of": date.today().isoformat(),
            "branch_count": payload.get("branch_count"),
            "branches": [
                {
                    "branch_id": b.get("branch_id"),
                    "success_rate": b.get("success_rate"),
                    "trust_score": b.get("trust_score"),
                    "retry_count": b.get("retry_count"),
                }
                for b in (payload.get("branches") or [])
            ],
        }
    )
    if len(runs) > 300:
        runs = runs[-300:]
    data["runs"] = runs
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)