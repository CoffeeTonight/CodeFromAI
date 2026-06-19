"""Child graph spec loader + evidence validation for multi-step parent nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml
from soc_verify.node_evidence import EvidenceResult, validate_step_evidence


CHILD_TRACE_NAME = "child_graph_trace.jsonl"
CHILD_EVIDENCE_NAME = "child_graph_evidence.json"


def child_spec_path(root: Path) -> Path:
    p = root / "registry" / "child_graph_spec.yaml"
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / "child_graph_spec.yaml"
    return p


def load_child_graph_spec(root: Path) -> dict[str, Any]:
    return load_yaml(child_spec_path(root))


def child_graphs_for_graph(spec: dict[str, Any], graph_id: str) -> dict[str, Any]:
    return (spec.get("child_graphs") or {}).get(graph_id) or {}


def record_child_step(
    run_dir: Path,
    *,
    parent_key: str,
    step_id: str,
    evidence: EvidenceResult | dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = evidence.to_dict() if isinstance(evidence, EvidenceResult) else evidence
    entry = {"parent": parent_key, "step": step_id, **payload}
    with (run_dir / CHILD_TRACE_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def validate_child_graph(
    root: Path,
    graph_id: str,
    child_key: str,
    *,
    state: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    spec = load_child_graph_spec(root)
    block = child_graphs_for_graph(spec, graph_id).get(child_key) or {}
    steps = block.get("steps") or []
    results: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        ev = validate_step_evidence(step, root=root, graph_id=graph_id, state=state, run_dir=run_dir)
        record_child_step(run_dir, parent_key=child_key, step_id=ev.step_id, evidence=ev)
        results.append(ev.to_dict())

    ok = all(r.get("ok") for r in results) if results else True
    return {
        "contract": "child_graph_evidence_v1",
        "graph": graph_id,
        "child_key": child_key,
        "ok": ok,
        "steps": results,
        "parent_function": block.get("parent_function"),
        "parent_nodes": block.get("parent_nodes"),
    }


def validate_all_child_graphs(
    root: Path,
    graph_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    spec = load_child_graph_spec(root)
    graphs = child_graphs_for_graph(spec, graph_id)
    reports: dict[str, Any] = {}
    for key in graphs:
        reports[key] = validate_child_graph(root, graph_id, key, state=state, run_dir=run_dir)
    summary = {
        "contract": "child_graph_summary_v1",
        "graph": graph_id,
        "all_ok": all(r.get("ok") for r in reports.values()),
        "children": reports,
    }
    (run_dir / CHILD_EVIDENCE_NAME).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "child_graph_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary