"""Milestone pipelines — ordered sub-steps compile to branch LangGraph specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml

SPEC_NAME = "milestone_pipeline_spec.yaml"


def spec_path(root: Path) -> Path:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return p


def load_pipeline_spec(root: Path) -> dict[str, Any]:
    return load_yaml(spec_path(root)) or {}


def list_pipelines(root: Path) -> list[dict[str, Any]]:
    spec = load_pipeline_spec(root)
    out: list[dict[str, Any]] = []
    for pid, block in (spec.get("pipelines") or {}).items():
        if isinstance(block, dict):
            out.append({"id": pid, **block})
    return out


def get_pipeline(root: Path, pipeline_id: str, *, project_id: str = "") -> dict[str, Any] | None:
    spec = load_pipeline_spec(root)
    block = (spec.get("pipelines") or {}).get(pipeline_id)
    if isinstance(block, dict):
        return {"id": pipeline_id, **block}
    if project_id:
        path = root / "projects" / project_id / "meta" / "pipeline_graphs" / f"{pipeline_id}.yaml"
        if path.is_file():
            data = load_yaml(path)
            if isinstance(data, dict):
                return {"id": pipeline_id, "project_id": project_id, **data}
    return _load_project_pipeline_any(root, pipeline_id)


def _load_project_pipeline_any(root: Path, pipeline_id: str) -> dict[str, Any] | None:
    projects = root / "projects"
    if not projects.is_dir():
        return None
    for proj in projects.iterdir():
        if not proj.is_dir():
            continue
        path = proj / "meta" / "pipeline_graphs" / f"{pipeline_id}.yaml"
        if path.is_file():
            data = load_yaml(path)
            if isinstance(data, dict):
                return {"id": pipeline_id, "project_id": proj.name, **data}
    return None


def validate_pipeline_order(pipeline: dict[str, Any], completed: set[str]) -> tuple[bool, list[str]]:
    """Check requires/predecessors satisfied for next node."""
    issues: list[str] = []
    nodes = pipeline.get("nodes") or {}
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        requires = list(node.get("requires") or [])
        for req in requires:
            if req not in completed:
                issues.append(f"{nid} requires {req} not completed")
    return not issues, issues


def next_pipeline_nodes(
    pipeline: dict[str, Any],
    *,
    completed: set[str],
    last_verdict: str = "PASS",
    last_node: str = "",
) -> list[str]:
    """Resolve edges + branches to determine next runnable nodes."""
    edges = pipeline.get("edges") or {}
    branches = pipeline.get("branches") or {}
    ordered = bool(pipeline.get("ordered", True))

    if last_node and last_verdict != "PASS":
        for bid, branch in branches.items():
            if not isinstance(branch, dict):
                continue
            when = branch.get("when") or {}
            if when.get("node") == last_node and last_verdict in (when.get("verdict_in") or []):
                goto = str(branch.get("goto", ""))
                if goto:
                    return [goto]

    if last_node and last_node in edges:
        candidates = list(edges[last_node])
        if "END" in candidates:
            candidates = [c for c in candidates if c != "END"]
        if ordered:
            return [c for c in candidates if c not in completed and c != "on_fail"]
        return candidates

    entry = str(pipeline.get("entry", ""))
    if entry and entry not in completed:
        return [entry]
    return []


def compile_branch_graph(pipeline: dict[str, Any]) -> dict[str, Any]:
    """Export pipeline as LangGraph-compatible branch spec for LLM/sub-agent compilation."""
    pid = str(pipeline.get("id", "pipeline"))
    nodes = pipeline.get("nodes") or {}
    return {
        "contract": "pipeline_branch_graph_v1",
        "pipeline_id": pid,
        "milestone": pipeline.get("milestone", ""),
        "ordered": pipeline.get("ordered", True),
        "entry": pipeline.get("entry", ""),
        "nodes": {
            nid: {
                "graph": node.get("graph", "verify_group"),
                "stage": node.get("stage", ""),
                "group": node.get("group", ""),
                "requires": node.get("requires", []),
                "refresh": node.get("refresh", {}),
            }
            for nid, node in nodes.items()
            if isinstance(node, dict)
        },
        "edges": pipeline.get("edges", {}),
        "branches": pipeline.get("branches", {}),
    }


def write_compiled_pipeline(project_dir: Path, pipeline: dict[str, Any]) -> Path:
    pid = str(pipeline.get("id", "pipeline"))
    out_dir = project_dir / "meta" / "pipeline_graphs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{pid}.yaml"
    save_yaml(path, compile_branch_graph(pipeline))
    return path


def pipelines_for_milestone(root: Path, milestone_id: str) -> list[dict[str, Any]]:
    return [p for p in list_pipelines(root) if str(p.get("milestone")) == milestone_id]