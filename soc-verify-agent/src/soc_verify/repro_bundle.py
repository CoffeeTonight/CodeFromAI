"""Reproduction bundle — LangGraph links + compressed small artifacts + purpose record."""

from __future__ import annotations

import hashlib
import json
import tarfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.repro_env import capture_env_pin, write_env_pin


BUNDLE_NAME = "repro_bundle.tar.gz"
MANIFEST_NAME = "repro_bundle_manifest.json"

# Large verification targets — link only, do not embed
LINK_ONLY_GLOBS = [
    "projects/*/verification/**/*.md",
    "projects/*/ops/**/*.py",
    "projects/*/bridge/**/*.py",
]

# LangGraph sources — always linked in manifest
LANGGRAPH_PATHS = [
    "src/soc_verify/graphs/verify_group.py",
    "src/soc_verify/graphs/orchestrator.py",
    "src/soc_verify/graphs/state.py",
    "src/soc_verify/graphs/orchestrator_state.py",
    "src/soc_verify/graphs/child_subgraphs.py",
    "registry/graph_flow_spec.yaml",
    "registry/node_contract.yaml",
    "registry/child_graph_spec.yaml",
    "registry/branch_scorecard_spec.yaml",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _link_entry(root: Path, rel: str) -> dict[str, Any]:
    p = root / rel
    if not p.is_file():
        return {"path": rel, "exists": False}
    return {
        "path": rel,
        "exists": True,
        "size_bytes": p.stat().st_size,
        "sha256_prefix": _sha256(p),
        "link": str(p.resolve()),
    }


def build_repro_manifest(
    root: Path,
    *,
    run_dir: Path,
    project_dir: Path | None,
    purpose: str,
    graph_id: str,
    run_id: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    langgraph_links = [_link_entry(root, rel) for rel in LANGGRAPH_PATHS]

    verification_links: list[dict[str, Any]] = []
    if project_dir and project_dir.is_dir():
        stage = str(state.get("stage", ""))
        group = str(state.get("group", ""))
        if stage and group:
            for name in ("CHECK.md", "RESPOND.md", "manifest.yaml"):
                rel = project_dir / "verification" / stage / group / name
                if rel.is_file():
                    verification_links.append(
                        {
                            "path": str(rel.relative_to(root)),
                            "link": str(rel.resolve()),
                            "sha256_prefix": _sha256(rel),
                            "embedded": False,
                            "reason": "large_verification_target",
                        }
                    )
        ops = project_dir / "ops" / stage / f"{group}.py" if stage and group else None
        if ops and ops.is_file():
            verification_links.append(
                {
                    "path": str(ops.relative_to(root)),
                    "link": str(ops.resolve()),
                    "sha256_prefix": _sha256(ops),
                    "embedded": False,
                }
            )

    env_pin = capture_env_pin(root)
    write_env_pin(run_dir, env_pin)

    small_artifacts: list[str] = []
    for name in (
        "experiment_run.json",
        "env_pin.json",
        "improvement_snapshot.json",
        "branch_scorecard.json",
        "child_graph_evidence.json",
        "improvement_ablation.json",
        "graph_trace.jsonl",
        "execution_log.jsonl",
        "llm_telemetry.jsonl",
        "workflow.json",
        "metrics.json",
        "parity_report.json",
        "meta_change_proposal.json",
    ):
        if (run_dir / name).is_file():
            small_artifacts.append(name)

    return {
        "contract": "repro_bundle_manifest_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": purpose,
        "graph_id": graph_id,
        "run_id": run_id,
        "project_id": state.get("project_id", ""),
        "stage": state.get("stage", ""),
        "group": state.get("group", ""),
        "langgraph_links": langgraph_links,
        "verification_links": verification_links,
        "embedded_artifacts": small_artifacts,
        "environment_pin": env_pin,
        "reproduce_intent": (
            f"Reproduce {graph_id} run {run_id} for "
            f"{state.get('project_id')}/{state.get('stage')}/{state.get('group')}: {purpose}"
        ),
    }


def build_repro_bundle(
    root: Path,
    run_dir: Path,
    manifest: dict[str, Any],
) -> Path:
    """Create tar.gz with manifest + small run artifacts (not large verification MD)."""
    bundle_path = run_dir / BUNDLE_NAME
    manifest_path = run_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(manifest_path, arcname=MANIFEST_NAME)
        for name in manifest.get("embedded_artifacts") or []:
            fp = run_dir / name
            if fp.is_file():
                tar.add(fp, arcname=f"artifacts/{name}")
        for extra in ("env_pin.json", "experiment_run.json", "llm_telemetry.jsonl"):
            fp = run_dir / extra
            if fp.is_file():
                tar.add(fp, arcname=f"artifacts/{extra}")
        trace = run_dir / "graph_trace.jsonl"
        if trace.is_file():
            tar.add(trace, arcname="artifacts/graph_trace.jsonl")
        backup = run_dir / "backup"
        if backup.is_dir():
            for bf in backup.rglob("*"):
                if bf.is_file():
                    tar.add(bf, arcname=str(bf.relative_to(run_dir)))

    return bundle_path