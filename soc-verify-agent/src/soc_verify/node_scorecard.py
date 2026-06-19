"""Per-node scorecard tracking — KPI time series for meta innovation loop."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.beci_formula import assess_node_intervention, beci_vector_from_signals
from soc_verify.models import load_yaml, save_yaml


REGISTRY_NAME = "node_scorecard_registry.yaml"


def registry_path(root: Path) -> Path:
    p = root / "registry" / REGISTRY_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / REGISTRY_NAME
    return p


def load_node_registry(root: Path) -> dict[str, Any]:
    return load_yaml(registry_path(root)) or {}


def iter_registered_nodes(root: Path) -> list[tuple[str, str]]:
    reg = load_node_registry(root)
    out: list[tuple[str, str]] = []
    for graph_id, block in (reg.get("graphs") or {}).items():
        for node_id in (block.get("nodes") or {}):
            out.append((str(graph_id), str(node_id)))
    return out


def _node_history_path(project_dir: Path, graph_id: str, node_id: str) -> Path:
    return project_dir / "scorecards" / "nodes" / graph_id / f"{node_id}.yaml"


def append_node_scorecard(
    project_dir: Path,
    *,
    graph_id: str,
    node_id: str,
    run_id: str,
    signals: dict[str, Any],
    events: dict[str, Any] | None = None,
    root: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    beci = beci_vector_from_signals(signals, events)
    trend_delta = dict(signals.get("delta_vs_previous") or {})
    assessment = assess_node_intervention(
        graph_id=graph_id,
        node_id=node_id,
        beci=beci,
        trend_delta=trend_delta,
        root=root,
    )
    entry = {
        "run_id": run_id,
        "as_of": date.today().isoformat(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "trust_score": float(signals.get("trust_score", 0.0)),
        "success_rate": 1.0 if signals.get("verdict") == "PASS" else 0.0,
        "completeness": float(signals.get("completeness", 0.0)),
        "verdict": str(signals.get("verdict", "")),
        "beci_vector": beci,
        "intervention_urgency": assessment.urgency,
        "intervene": assessment.intervene,
        "retry_count": int(signals.get("fix_round", 0)),
    }
    if extra:
        entry.update(extra)

    path = _node_history_path(project_dir, graph_id, node_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path) if path.is_file() else {"contract": "node_scorecard_v1", "graph": graph_id, "node": node_id, "entries": []}
    data.setdefault("entries", []).append(entry)
    if len(data["entries"]) > 200:
        data["entries"] = data["entries"][-200:]
    save_yaml(path, data)
    return entry


def load_node_trend(project_dir: Path, graph_id: str, node_id: str, *, last_n: int = 10) -> list[dict[str, Any]]:
    path = _node_history_path(project_dir, graph_id, node_id)
    if not path.is_file():
        return []
    data = load_yaml(path)
    entries = list(data.get("entries") or [])
    return entries[-last_n:]


def collect_all_node_observations(
    project_dir: Path,
    root: Path,
    *,
    last_n: int = 5,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for graph_id, node_id in iter_registered_nodes(root):
        trend = load_node_trend(project_dir, graph_id, node_id, last_n=last_n)
        if not trend:
            continue
        latest = trend[-1]
        urgencies = [float(e.get("intervention_urgency", 0)) for e in trend]
        observations.append(
            {
                "graph_id": graph_id,
                "node_id": node_id,
                "latest": latest,
                "urgency_trend": urgencies,
                "urgency_delta": round(urgencies[-1] - urgencies[0], 4) if len(urgencies) > 1 else 0.0,
                "sample_count": len(trend),
            }
        )
    return {
        "contract": "node_observations_v1",
        "project_id": project_dir.name,
        "observations": observations,
        "high_urgency": [o for o in observations if float(o["latest"].get("intervention_urgency", 0)) >= 0.45],
    }