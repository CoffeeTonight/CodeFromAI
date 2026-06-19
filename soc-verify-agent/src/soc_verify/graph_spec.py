"""Load LangGraph flow specification — LLM-readable flow document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml


def spec_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    p = root / "registry" / "graph_flow_spec.yaml"
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / "graph_flow_spec.yaml"
    return p


def load_flow_spec(root: Path | None = None) -> dict[str, Any]:
    return load_yaml(spec_path(root))


def node_spec(spec: dict[str, Any], graph_id: str, node_id: str) -> dict[str, Any] | None:
    graphs = spec.get("graphs") or {}
    g = graphs.get(graph_id) or {}
    nodes = g.get("nodes") or {}
    block = nodes.get(node_id)
    if not block:
        return None
    return {"graph": graph_id, "node": node_id, **block}


def next_nodes_from_spec(spec: dict[str, Any], graph_id: str, node_id: str) -> list[str]:
    graphs = spec.get("graphs") or {}
    edges = (graphs.get(graph_id) or {}).get("edges") or {}
    return list(edges.get(node_id) or [])


def topology_from_spec(spec: dict[str, Any], graph_id: str) -> dict[str, Any]:
    """Derive LLM topology hint from graph_flow_spec — single source of truth."""
    graphs = spec.get("graphs") or {}
    g = graphs.get(graph_id) or {}
    node_defs = g.get("nodes") or {}
    nodes = list(node_defs.keys()) if isinstance(node_defs, dict) else list(node_defs)
    topo: dict[str, Any] = {
        "graph": graph_id,
        "entry": str(g.get("entry") or (nodes[0] if nodes else "")),
        "nodes": nodes,
        "edges": dict(g.get("edges") or {}),
    }
    if graph_id == "verify_group":
        topo["runner_loop_diagram"] = "templates/obsidian/08-RUNNER-LOOP.md"
    elif graph_id == "setup_group":
        topo["adaptive_setup_diagram"] = "templates/llm/system_setup_adaptive.txt"
    return topo


def api_endpoints(spec: dict[str, Any], *, root: str = ".", host: str = "127.0.0.1", port: int = 8765) -> dict[str, str]:
    api = spec.get("api") or {}
    cli = str(api.get("cli_base", "soc-verify graph")).format(root=root)
    http = str(api.get("http_base", "http://127.0.0.1:8765/graph")).format(host=host, port=port)
    eps = api.get("endpoints") or {}
    return {
        "cli_base": cli,
        "http_base": http,
        "spec": f"{http}{eps.get('spec', '/spec')}",
        "start": f"{http}{eps.get('start', '/sessions')}",
        "status": f"{http}{eps.get('status', '/sessions/{{session_id}}')}",
        "tick": f"{http}{eps.get('tick', '/sessions/{{session_id}}/tick')}",
        "resume": f"{http}{eps.get('resume', '/sessions/{{session_id}}/resume')}",
        "invoke_llm": f"{http}{eps.get('invoke_llm', '/sessions/{{session_id}}/invoke-llm')}",
        "sandbox": f"{http}{eps.get('sandbox', '/sessions/{{session_id}}/sandbox')}",
    }