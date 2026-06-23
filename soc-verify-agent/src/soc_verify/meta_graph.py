"""Meta-graph — structured change proposals; graph source never auto-applied."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from soc_verify.improvement_eval import summarize_trend
from soc_verify.models import load_yaml, save_yaml


Layer = Literal["md", "ops", "bridge", "graph_spec", "node_contract", "graph_source", "policy"]

# Defense-in-depth — never auto-apply regardless of meta_graph_spec auto_apply flags.
NEVER_AUTO_APPLY_LAYERS = frozenset({"graph_source", "graph_spec", "node_contract", "policy"})

META_PROPOSAL_NAME = "meta_change_proposal.json"
META_QUEUE_NAME = "meta_change_queued.json"


def meta_spec_path(root: Path) -> Path:
    p = root / "registry" / "meta_graph_spec.yaml"
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / "meta_graph_spec.yaml"
    return p


def load_meta_spec(root: Path) -> dict[str, Any]:
    return load_yaml(meta_spec_path(root))


def build_meta_collect_payload(
    *,
    root: Path,
    project_dir: Path,
    run_dir: Path,
    signals: dict[str, Any],
    snapshot: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    spec = load_meta_spec(root)
    stage = str(signals.get("stage", ""))
    group = str(signals.get("group", ""))
    trend = summarize_trend(project_dir, stage, group)

    change_hints: list[dict[str, Any]] = []
    if signals.get("verdict") != "PASS":
        change_hints.append(
            {
                "layer": "md" if signals.get("error_kind") == "verification" else "bridge",
                "reason": f"verdict={signals.get('verdict')} error_kind={signals.get('error_kind')}",
                "suggested_targets": [
                    f"verification/{stage}/{group}/CHECK.md",
                    f"ops/{stage}/{group}.py",
                ],
            }
        )
    if signals.get("parity_ok") is False:
        change_hints.append(
            {
                "layer": "ops",
                "reason": "parity_fail",
                "suggested_targets": [f"ops/{stage}/{group}.py"],
            }
        )
    if signals.get("stalemate"):
        change_hints.append(
            {
                "layer": "graph_spec",
                "reason": "stalemate_loop_guard",
                "suggested_targets": ["registry/graph_flow_spec.yaml", "registry/node_contract.yaml"],
                "approval": "human_required",
            }
        )
    if int(signals.get("llm_node_count", 0)) >= 5:
        change_hints.append(
            {
                "layer": "graph_spec",
                "reason": "high_llm_node_count",
                "suggested_targets": ["registry/graph_flow_spec.yaml"],
                "approval": "human_required",
            }
        )

    trace_path = run_dir / "graph_trace.jsonl"
    trace_nodes: list[str] = []
    if trace_path.is_file():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    trace_nodes.append(str(json.loads(line).get("node", "")))
                except json.JSONDecodeError:
                    pass

    return {
        "contract": "meta_collect_v1",
        "meta_spec": str(meta_spec_path(root)),
        "run_id": signals.get("run_id"),
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "improvement_signal": signals,
        "improvement_snapshot": snapshot,
        "trend": trend,
        "graph_trace_nodes": trace_nodes,
        "change_hints": change_hints,
        "branch_scorecard": str(run_dir / "branch_scorecard.json"),
        "child_graph_evidence": str(run_dir / "child_graph_evidence.json"),
        "allowed_layers": list((spec.get("layers") or {}).keys()),
        "instruction": (
            "Propose changes ONLY for layers/targets in meta_graph_spec. "
            "graph_source requires human approval — never direct edit. "
            "Each change must cite evidence from improvement_snapshot deltas."
        ),
    }


def write_meta_collect_prompt(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / "meta_collect_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_empty_meta_proposal(
    run_dir: Path,
    *,
    run_id: str,
    reason: str = "no_changes",
) -> Path:
    """Stub when LLM absent — satisfies exit contract; queue will reject empty changes."""
    path = run_dir / META_PROPOSAL_NAME
    payload = {
        "contract": "meta_change_proposal_v1",
        "run_id": run_id,
        "summary": reason,
        "changes": [],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_mechanical_meta_proposal(
    run_dir: Path,
    *,
    run_id: str,
    stage: str,
    group: str,
    root: Path,
) -> tuple[Path, dict[str, Any]]:
    """Valid no-op proposal for stub/E2E — passes schema; queue for human review only."""
    target = f"verification/{stage}/{group}/RUN.md"
    proposal: dict[str, Any] = {
        "contract": "meta_change_proposal_v1",
        "run_id": run_id,
        "summary": "mechanical_stub — schema-valid placeholder; no auto-apply",
        "changes": [
            {
                "layer": "md",
                "target": target,
                "rationale": "mechanical_stub_for_meta_queue",
                "evidence": ["improvement_snapshot"],
                "approval": "human_or_review",
            }
        ],
    }
    spec = load_meta_spec(root)
    validation = validate_meta_proposal(proposal, spec)
    path = run_dir / META_PROPOSAL_NAME
    path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    return path, validation


def ensure_meta_queue_artifact(
    project_dir: Path,
    run_dir: Path,
    *,
    root: Path,
) -> dict[str, Any]:
    """Write meta_change_queued.json if missing — mechanical or from on-disk proposal."""
    queued_path = run_dir / META_QUEUE_NAME
    if queued_path.is_file():
        return json.loads(queued_path.read_text(encoding="utf-8"))

    proposal = load_meta_proposal(run_dir)
    if proposal is None:
        write_mechanical_meta_proposal(
            run_dir,
            run_id=run_dir.name,
            stage="simulation",
            group="unknown",
            root=root,
        )
        proposal = load_meta_proposal(run_dir)
    assert proposal is not None

    changes = proposal.get("changes") or []
    if not changes:
        stage = str(proposal.get("stage") or "simulation")
        group = str(proposal.get("group") or "gpio_ext")
        write_mechanical_meta_proposal(
            run_dir,
            run_id=str(proposal.get("run_id", run_dir.name)),
            stage=stage,
            group=group,
            root=root,
        )
        proposal = load_meta_proposal(run_dir)
        assert proposal is not None

    validation = validate_meta_proposal(proposal, load_meta_spec(root))
    return queue_meta_proposal(project_dir, run_dir, proposal, validation)


def load_meta_proposal(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / META_PROPOSAL_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_meta_proposal(proposal: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    changes = proposal.get("changes") or []
    if not changes:
        issues.append("no_changes_listed")

    layers = spec.get("layers") or {}
    for i, ch in enumerate(changes):
        if not isinstance(ch, dict):
            issues.append(f"change_{i}_not_object")
            continue
        layer = str(ch.get("layer", ""))
        target = str(ch.get("target", ""))
        if layer not in layers:
            issues.append(f"change_{i}_layer_forbidden:{layer}")
            continue
        layer_spec = layers[layer]
        if layer_spec.get("auto_apply") is False:
            layer_approval = str(layer_spec.get("approval", "human_required"))
            ch_approval = str(ch.get("approval", ""))
            if layer_approval == "human_or_review":
                if ch_approval not in ("human_required", "human_or_review"):
                    issues.append(f"change_{i}_requires_human:{layer}")
            elif ch_approval != "human_required":
                issues.append(f"change_{i}_requires_human:{layer}")
        patterns = layer_spec.get("target_globs") or []
        if patterns and target:
            from fnmatch import fnmatch

            if not any(fnmatch(target.replace("\\", "/"), p) for p in patterns):
                issues.append(f"change_{i}_target_not_allowed:{target}")

    return {"ok": not issues, "issues": issues, "contract": "meta_validate_v1"}


def queue_meta_proposal(
    project_dir: Path,
    run_dir: Path,
    proposal: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    queue_dir = project_dir / "meta_proposals"
    queue_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(proposal.get("run_id", run_dir.name))
    record = {
        "queued_at": date.today().isoformat(),
        "run_id": run_id,
        "validation": validation,
        "proposal": proposal,
        "status": "queued" if validation.get("ok") else "rejected",
    }
    out = queue_dir / f"{run_id}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / META_QUEUE_NAME).write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    root = project_dir.parent.parent
    try:
        from soc_verify.platform_telemetry import record_code_change

        for ch in proposal.get("changes") or []:
            if not isinstance(ch, dict):
                continue
            record_code_change(
                root,
                run_id=run_id,
                project_id=project_dir.name,
                layer=str(ch.get("layer", "")),
                target=str(ch.get("target", "")),
                rationale=str(ch.get("rationale", "")),
                source="meta_proposal_queue",
                applied=bool(validation.get("ok")),
            )
    except Exception:
        pass

    return {"queued": validation.get("ok"), "path": str(out), "status": record["status"]}


def layer_auto_apply_allowed(
    layer: str,
    *,
    layer_spec: dict[str, Any],
    policies: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Code-level guard — policies.graph_source_never_auto_apply is enforced here."""
    if layer in NEVER_AUTO_APPLY_LAYERS:
        return False, "never_auto_apply_layer"
    meta_pol = (policies or {}).get("meta_graph") or {}
    if meta_pol.get("graph_source_never_auto_apply", True) and layer == "graph_source":
        return False, "graph_source_never_auto_apply"
    if not layer_spec.get("auto_apply"):
        return False, "no_auto_apply"
    return True, "ok"


def apply_low_risk_artifacts(
    project_dir: Path,
    proposal: dict[str, Any],
    spec: dict[str, Any],
    *,
    policies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply md/ops/bridge only when layer allows auto_apply and content provided."""
    applied: list[str] = []
    skipped: list[str] = []
    layers = spec.get("layers") or {}

    for ch in proposal.get("changes") or []:
        if not isinstance(ch, dict):
            continue
        layer = str(ch.get("layer", ""))
        layer_spec = layers.get(layer) or {}
        allowed, reason = layer_auto_apply_allowed(layer, layer_spec=layer_spec, policies=policies)
        if not allowed:
            skipped.append(f"{layer}:{ch.get('target')}:{reason}")
            continue
        content = ch.get("content")
        if not content or not isinstance(content, str):
            skipped.append(f"{layer}:{ch.get('target')}:no_content")
            continue
        target = Path(str(ch.get("target", "")))
        if target.is_absolute():
            skipped.append(f"{layer}:{target}:absolute_path")
            continue
        dest = project_dir / target
        if layer == "md" and not str(target).startswith("verification/"):
            skipped.append(f"{layer}:{target}:not_verification_md")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        applied.append(str(dest.relative_to(project_dir)))

    return {"applied": applied, "skipped": skipped}