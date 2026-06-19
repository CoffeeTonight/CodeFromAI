"""Self-improvement KPIs — per-run snapshot and delta vs history."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml


HISTORY_NAME = "history.yaml"
SNAPSHOT_NAME = "improvement_snapshot.json"
SIGNAL_NAME = "improvement_signal.json"


@dataclass
class ImprovementSnapshot:
    run_id: str
    project_id: str
    stage: str
    group: str
    as_of: str
    verdict: str
    completeness: float
    trust_score: float
    runner: str
    runner_mode: str
    fix_round: int
    codegen_round: int
    bridge_round: int
    error_kind: str
    parity_ok: bool | None
    llm_node_count: int
    graph_step_count: int
    stalemate: bool
    promoted: bool
    llm_fix_rounds: int
    tool_incidents: int
    env_fail_steps: int
    improvement_index: float = 0.0
    delta_vs_previous: dict[str, float] = field(default_factory=dict)
    delta_vs_baseline: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "improvement_snapshot_v1",
            "run_id": self.run_id,
            "project_id": self.project_id,
            "stage": self.stage,
            "group": self.group,
            "as_of": self.as_of,
            "verdict": self.verdict,
            "completeness": self.completeness,
            "trust_score": self.trust_score,
            "runner": self.runner,
            "runner_mode": self.runner_mode,
            "fix_round": self.fix_round,
            "codegen_round": self.codegen_round,
            "bridge_round": self.bridge_round,
            "error_kind": self.error_kind,
            "parity_ok": self.parity_ok,
            "llm_node_count": self.llm_node_count,
            "graph_step_count": self.graph_step_count,
            "stalemate": self.stalemate,
            "promoted": self.promoted,
            "llm_fix_rounds": self.llm_fix_rounds,
            "tool_incidents": self.tool_incidents,
            "env_fail_steps": self.env_fail_steps,
            "improvement_index": self.improvement_index,
            "delta_vs_previous": self.delta_vs_previous,
            "delta_vs_baseline": self.delta_vs_baseline,
        }


def _improvement_dir(project_dir: Path) -> Path:
    d = project_dir / "improvement"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _count_graph_trace_nodes(run_dir: Path) -> tuple[int, int]:
    path = run_dir / "graph_trace.jsonl"
    if not path.is_file():
        return 0, 0
    llm_nodes = {
        "run_gate",
        "run_codegen",
        "diagnose_env",
        "promote",
        "finalize_reproduction",
        "meta_propose",
    }
    llm_count = 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(entry.get("node", "")) in llm_nodes:
            llm_count += 1
    return llm_count, total


def _load_parity_ok(run_dir: Path) -> bool | None:
    path = run_dir / "parity_report.json"
    if not path.is_file():
        return None
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("ok"))
    except json.JSONDecodeError:
        return None


def collect_run_signals(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    events = dict(state.get("events") or {})
    llm_nodes, graph_steps = _count_graph_trace_nodes(run_dir)
    promote_out = state.get("promote_outcome") or {}
    return {
        "contract": "improvement_signal_v1",
        "run_id": state.get("run_id", run_dir.name),
        "project_id": state.get("project_id", ""),
        "stage": state.get("stage", ""),
        "group": state.get("group", ""),
        "verdict": state.get("verdict", "UNKNOWN"),
        "completeness": float(state.get("completeness", 0.0)),
        "trust_score": float(state.get("trust_score", 0.0)),
        "runner": state.get("runner", ""),
        "runner_mode": state.get("runner_mode", ""),
        "fix_round": int(state.get("fix_round", 0)),
        "codegen_round": int(state.get("codegen_round", 0)),
        "bridge_round": int(state.get("bridge_round", 0)),
        "error_kind": state.get("error_kind", ""),
        "parity_ok": state.get("parity_ok", _load_parity_ok(run_dir)),
        "stalemate": bool(state.get("stalemate")),
        "promoted": bool(promote_out.get("promoted")),
        "llm_node_count": llm_nodes,
        "graph_step_count": graph_steps,
        "llm_fix_rounds": int(events.get("llm_fix_rounds", 0)),
        "tool_incidents": int(events.get("tool_incidents", 0)),
        "env_fail_steps": int(events.get("env_fail_steps", 0)),
        "questions_count": len(state.get("questions") or []),
        "continue_improvement": bool(state.get("continue_improvement")),
    }


def write_improvement_signal(run_dir: Path, signals: dict[str, Any]) -> Path:
    path = run_dir / SIGNAL_NAME
    path.write_text(json.dumps(signals, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _metric_vector(snap: dict[str, Any]) -> dict[str, float]:
    verdict_pass = 1.0 if snap.get("verdict") == "PASS" else 0.0
    parity = snap.get("parity_ok")
    parity_ok = 1.0 if parity is True else (0.0 if parity is False else 0.5)
    runner_py = 1.0 if snap.get("runner") == "python" else 0.0
    return {
        "completeness": float(snap.get("completeness", 0.0)),
        "trust_score": float(snap.get("trust_score", 0.0)),
        "verdict_pass": verdict_pass,
        "parity_ok": parity_ok,
        "runner_python": runner_py,
        "llm_efficiency": max(0.0, 1.0 - float(snap.get("llm_node_count", 0)) / 10.0),
        "fix_round_inv": max(0.0, 1.0 - float(snap.get("fix_round", 0)) / 10.0),
        "tool_incident_inv": max(0.0, 1.0 - float(snap.get("tool_incidents", 0)) / 5.0),
    }


def _compute_delta(current: dict[str, float], other: dict[str, float]) -> dict[str, float]:
    keys = set(current) | set(other)
    return {k: round(current.get(k, 0.0) - other.get(k, 0.0), 4) for k in keys}


def _improvement_index(vector: dict[str, float], delta_prev: dict[str, float]) -> float:
    base = (
        0.25 * vector.get("completeness", 0.0)
        + 0.20 * vector.get("trust_score", 0.0)
        + 0.15 * vector.get("verdict_pass", 0.0)
        + 0.10 * vector.get("parity_ok", 0.0)
        + 0.10 * vector.get("runner_python", 0.0)
        + 0.10 * vector.get("llm_efficiency", 0.0)
        + 0.05 * vector.get("fix_round_inv", 0.0)
        + 0.05 * vector.get("tool_incident_inv", 0.0)
    )
    trend = sum(delta_prev.get(k, 0.0) for k in ("completeness", "trust_score", "verdict_pass", "parity_ok")) / 4.0
    return round(min(1.0, max(0.0, base + 0.15 * trend)), 4)


def load_history(project_dir: Path, stage: str, group: str) -> list[dict[str, Any]]:
    path = _improvement_dir(project_dir) / HISTORY_NAME
    data = load_yaml(path)
    key = f"{stage}/{group}"
    entries = (data.get("groups") or {}).get(key) or []
    return list(entries) if isinstance(entries, list) else []


def build_snapshot(
    project_dir: Path,
    run_dir: Path,
    signals: dict[str, Any],
    *,
    as_of: str | None = None,
) -> ImprovementSnapshot:
    vector = _metric_vector(signals)
    history = load_history(project_dir, signals["stage"], signals["group"])
    prev = history[-1] if history else None
    baseline = history[0] if history else None

    delta_prev = _compute_delta(vector, _metric_vector(prev)) if prev else {}
    delta_base = _compute_delta(vector, _metric_vector(baseline)) if baseline else {}

    snap = ImprovementSnapshot(
        run_id=str(signals.get("run_id", run_dir.name)),
        project_id=str(signals.get("project_id", project_dir.name)),
        stage=str(signals["stage"]),
        group=str(signals["group"]),
        as_of=as_of or date.today().isoformat(),
        verdict=str(signals.get("verdict", "UNKNOWN")),
        completeness=float(signals.get("completeness", 0.0)),
        trust_score=float(signals.get("trust_score", 0.0)),
        runner=str(signals.get("runner", "")),
        runner_mode=str(signals.get("runner_mode", "")),
        fix_round=int(signals.get("fix_round", 0)),
        codegen_round=int(signals.get("codegen_round", 0)),
        bridge_round=int(signals.get("bridge_round", 0)),
        error_kind=str(signals.get("error_kind", "")),
        parity_ok=signals.get("parity_ok"),
        llm_node_count=int(signals.get("llm_node_count", 0)),
        graph_step_count=int(signals.get("graph_step_count", 0)),
        stalemate=bool(signals.get("stalemate")),
        promoted=bool(signals.get("promoted")),
        llm_fix_rounds=int(signals.get("llm_fix_rounds", 0)),
        tool_incidents=int(signals.get("tool_incidents", 0)),
        env_fail_steps=int(signals.get("env_fail_steps", 0)),
        delta_vs_previous=delta_prev,
        delta_vs_baseline=delta_base,
    )
    snap.improvement_index = _improvement_index(vector, delta_prev)
    return snap


BRANCH_HISTORY_NAME = "branch_history.yaml"


def append_branch_history(
    project_dir: Path,
    *,
    run_id: str,
    stage: str,
    group: str,
    branch_scorecard: dict[str, Any],
) -> None:
    """Merge per-branch scorecard rollups into improvement time series."""
    path = _improvement_dir(project_dir) / BRANCH_HISTORY_NAME
    data = load_yaml(path)
    if not data:
        data = {"contract": "branch_history_v1", "groups": {}}
    key = f"{stage}/{group}"
    groups = data.setdefault("groups", {})
    entries = list(groups.get(key) or [])
    branches = branch_scorecard.get("branches") or []
    entries.append(
        {
            "run_id": run_id,
            "as_of": date.today().isoformat(),
            "branch_count": len(branches),
            "mean_success_rate": round(
                sum(float(b.get("success_rate", 0)) for b in branches) / max(1, len(branches)),
                4,
            ),
            "mean_trust": round(
                sum(float(b.get("trust_score", 0)) for b in branches) / max(1, len(branches)),
                4,
            ),
            "branches": [
                {
                    "branch_id": b.get("branch_id"),
                    "success_rate": b.get("success_rate"),
                    "trust_score": b.get("trust_score"),
                    "retry_count": b.get("retry_count"),
                }
                for b in branches
            ],
        }
    )
    if len(entries) > 200:
        entries = entries[-200:]
    groups[key] = entries
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)


def append_history(project_dir: Path, snapshot: ImprovementSnapshot) -> None:
    path = _improvement_dir(project_dir) / HISTORY_NAME
    data = load_yaml(path)
    if not data:
        data = {"contract": "improvement_history_v1", "groups": {}}
    key = f"{snapshot.stage}/{snapshot.group}"
    groups = data.setdefault("groups", {})
    entries = list(groups.get(key) or [])
    entries.append(snapshot.to_dict())
    if len(entries) > 200:
        entries = entries[-200:]
    groups[key] = entries
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)


def write_improvement_snapshot(run_dir: Path, snapshot: ImprovementSnapshot) -> Path:
    path = run_dir / SNAPSHOT_NAME
    path.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def summarize_trend(project_dir: Path, stage: str, group: str) -> dict[str, Any]:
    history = load_history(project_dir, stage, group)
    if len(history) < 2:
        return {"trend": "insufficient_data", "runs": len(history)}
    last = history[-1]
    prev = history[-2]
    improving = float(last.get("improvement_index", 0)) >= float(prev.get("improvement_index", 0))
    return {
        "trend": "improving" if improving else "regressing",
        "runs": len(history),
        "last_index": last.get("improvement_index"),
        "delta_index": round(
            float(last.get("improvement_index", 0)) - float(prev.get("improvement_index", 0)),
            4,
        ),
        "delta_completeness": (last.get("delta_vs_previous") or {}).get("completeness"),
    }