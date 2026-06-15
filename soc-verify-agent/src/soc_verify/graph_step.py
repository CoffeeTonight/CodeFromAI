"""LangGraph step contract — machine-readable position for LLM (not graph source code)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Static topology reference (platform). LLM reads graph_step.json per run, not this file.
VERIFY_GROUP_TOPOLOGY: dict[str, Any] = {
    "graph": "verify_group",
    "entry": "setup",
    "nodes": [
        "setup",
        "load_context",
        "select_runner",
        "run_gate",
        "diagnose_env",
        "patch_bridge",
        "evaluate",
        "parity_check",
        "run_codegen",
        "promote",
        "finalize_reproduction",
        "finalize",
    ],
    "edges": {
        "load_context": ["select_runner", "finalize"],
        "run_gate": ["select_runner", "evaluate", "diagnose_env", "finalize"],
        "diagnose_env": ["patch_bridge", "finalize"],
        "patch_bridge": ["select_runner"],
        "evaluate": ["select_runner", "parity_check", "finalize"],
        "parity_check": ["promote", "run_codegen", "finalize"],
        "run_codegen": ["parity_check"],
        "promote": ["finalize_reproduction"],
        "finalize_reproduction": ["finalize"],
    },
    "runner_loop_diagram": "templates/obsidian/08-RUNNER-LOOP.md",
}

ORCHESTRATOR_TOPOLOGY: dict[str, Any] = {
    "graph": "orchestrator",
    "entry": "setup",
    "nodes": [
        "setup",
        "plan_work",
        "run_acquisition",
        "prepare_verify",
        "dispatch_verify",
        "advance_work",
        "finalize_reproduction_sequence",
        "finalize",
    ],
    "edges": {
        "dispatch_verify": ["advance_work", "finalize_reproduction_sequence"],
        "advance_work": ["run_acquisition", "prepare_verify", "finalize_reproduction_sequence"],
        "finalize_reproduction_sequence": ["finalize"],
    },
}


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
        "topology_hint": VERIFY_GROUP_TOPOLOGY if graph == "verify_group" else ORCHESTRATOR_TOPOLOGY,
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