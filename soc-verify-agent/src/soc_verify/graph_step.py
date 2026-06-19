"""LangGraph step contract — machine-readable position for LLM (not graph source code)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc_verify.graph_spec import load_flow_spec, topology_from_spec


def topology_hint_for_graph(graph: str, root: Path | None = None) -> dict[str, Any]:
    spec = load_flow_spec(root)
    if graph in spec.get("graphs", {}):
        return topology_from_spec(spec, graph)
    return topology_from_spec(spec, "orchestrator")


def write_graph_step(
    run_dir: Path,
    *,
    graph: str,
    node: str,
    group: str,
    stage: str,
    runner: str = "llm",
    fix_round: int = 0,
    orchestrator_run_id: str = "",
    extra: dict[str, Any] | None = None,
    root: Path | None = None,
) -> Path:
    payload: dict[str, Any] = {
        "source": "langgraph",
        "graph": graph,
        "node": node,
        "stage": stage,
        "group": group,
        "runner": runner,
        "fix_round": fix_round,
        "orchestrator_run_id": orchestrator_run_id,
        "required_artifacts": [f"verdict_{group}.json"],
        "optional_artifacts": ["sub_stop.json"],
        "topology_hint": topology_hint_for_graph(graph, root),
        "rules": [
            "Read md_only_prompt.json for verification MD only",
            "Read templates/obsidian/08-RUNNER-LOOP.md — mandatory runner loop",
            "Follow graph transitions; do not skip nodes (parity_check enforced in code)",
            "PASS requires verdict JSON on disk",
            "promote requires parity_report.json ok:true (or python_canonical skip)",
        ],
    }
    if extra:
        payload.update(extra)

    path = run_dir / "graph_step.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def append_graph_trace(run_dir: Path, entry: dict[str, Any]) -> None:
    trace_path = run_dir / "graph_trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")