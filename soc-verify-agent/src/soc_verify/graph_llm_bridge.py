"""LangGraph → Company LLM API. Graph calls LLM with flow spec + graph API callbacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc_verify.config import load_user_config
from soc_verify.graph_spec import api_endpoints, load_flow_spec, node_spec
from soc_verify.node_contract import sandbox_payload_for_node, validate_exit_contract
from soc_verify.node_gate import enrich_sandbox_payload, node_gate_payload
from soc_verify.node_triage import triage_payload
from soc_verify.llm_runner import LlmInvokeResult, _read_template, invoke_llm_chat


def build_graph_llm_payload(
    *,
    root: Path,
    session_id: str,
    graph_id: str,
    node_id: str,
    state_snapshot: dict[str, Any],
    run_dir: Path | None = None,
    http_host: str = "127.0.0.1",
    http_port: int = 8765,
) -> dict[str, Any]:
    spec = load_flow_spec(root)
    ns = node_spec(spec, graph_id, node_id) or {}
    apis = api_endpoints(spec, root=str(root.resolve()), host=http_host, port=http_port)
    graph_slice = (spec.get("graphs") or {}).get(graph_id) or {}

    payload: dict[str, Any] = {
        "contract": "langgraph_flow_driver",
        "instruction": (spec.get("instruction_ko") or "").strip(),
        "flow_spec_file": str((root / "registry" / "graph_flow_spec.yaml").resolve()),
        "flow_spec": {
            "version": spec.get("version"),
            "graphs": {graph_id: graph_slice},
        },
        "current": {
            "graph": graph_id,
            "node": node_id,
            "node_spec": ns,
            "session_id": session_id,
        },
        "state_snapshot": {
            k: state_snapshot.get(k)
            for k in (
                "project_id",
                "stage",
                "group",
                "runner",
                "verdict",
                "fix_round",
                "round",
                "info_gap",
                "milestone_plan",
                "current_milestone",
                "user_skillset",
                "skills_registered",
                "skill_ids",
                "validation_sequence_action",
            )
            if k in state_snapshot
        },
        "graph_api": {
            **apis,
            "session_id": session_id,
            "cli_tick": f"soc-verify --root {root} graph tick --session {session_id}",
            "cli_resume": f"soc-verify --root {root} graph resume --session {session_id}",
            "cli_status": f"soc-verify --root {root} graph status --session {session_id}",
        },
        "llm_contract": spec.get("llm_contract"),
        "node_contract_file": str((root / "registry" / "node_contract.yaml").resolve()),
    }

    payload["node_sandbox"] = enrich_sandbox_payload(
        sandbox_payload_for_node(
            root,
            graph_id,
            node_id,
            state=state_snapshot,
            run_dir=run_dir,
        )
    )
    try:
        gate_cfg = load_user_config(root)
    except FileNotFoundError:
        gate_cfg = None
    payload["node_gate"] = node_gate_payload(
        root,
        graph_id,
        node_id,
        state=state_snapshot,
        run_dir=run_dir,
        config=gate_cfg,
    )
    payload["exit_contract"] = validate_exit_contract(
        root,
        graph_id,
        node_id,
        state=state_snapshot,
        run_dir=run_dir,
    ).to_dict()
    payload["node_triage"] = triage_payload(
        root,
        graph_id,
        node_id,
        state=state_snapshot,
        run_dir=run_dir,
        config=gate_cfg,
    )

    if run_dir and run_dir.is_dir():
        md = run_dir / "md_only_prompt.md"
        if md.is_file():
            payload["md_only_prompt_md"] = md.read_text(encoding="utf-8")
        step = run_dir / "graph_step.json"
        if step.is_file():
            payload["graph_step"] = json.loads(step.read_text(encoding="utf-8"))

    return payload


def invoke_llm_from_graph(
    *,
    root: Path,
    session_id: str,
    graph_id: str,
    node_id: str,
    state_snapshot: dict[str, Any],
    run_dir: Path | None = None,
    config: UserConfig | None = None,
) -> LlmInvokeResult:
    """LangGraph node boundary → unified LLM dispatch (openai_compatible / http / script)."""
    if config is None:
        try:
            config = load_user_config(root)
        except FileNotFoundError:
            config = UserConfig(raw={"llm": {"mode": "stub"}}, path=root / "config.json")

    payload = build_graph_llm_payload(
        root=root,
        session_id=session_id,
        graph_id=graph_id,
        node_id=node_id,
        state_snapshot=state_snapshot,
        run_dir=run_dir,
    )

    out_dir = root / "runs" / "graph_sessions" / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    invoke_path = out_dir / f"llm_invoke_{node_id}.json"
    invoke_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if graph_id == "setup_group":
        template_name = "system_setup_adaptive.txt"
    elif graph_id == "meta_innovation_loop":
        template_name = "system_meta_innovation.txt"
    else:
        template_name = "system_graph_driver.txt"
    system = _read_template(template_name)
    if not system:
        system = (
            "You are the SoC verification agent. Follow registry/graph_flow_spec.yaml exactly. "
            "Use graph_api endpoints to tick/resume after each node. "
            "Verification logic: md_only_prompt_md only."
        )

    return invoke_llm_chat(
        config,
        root=root,
        task="graph_driver",
        system=system,
        user_content=json.dumps(payload, ensure_ascii=False),
        http_task="langgraph_flow_driver",
        endpoint_keys=("graph_endpoint", "endpoint"),
    )