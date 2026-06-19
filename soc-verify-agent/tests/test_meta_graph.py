from __future__ import annotations

import json
import uuid
from pathlib import Path

from soc_verify.meta_graph import (
    META_PROPOSAL_NAME,
    META_QUEUE_NAME,
    build_meta_collect_payload,
    ensure_meta_queue_artifact,
    load_meta_spec,
    queue_meta_proposal,
    validate_meta_proposal,
    write_empty_meta_proposal,
    write_mechanical_meta_proposal,
    write_meta_collect_prompt,
)
from soc_verify.node_contract import validate_transition


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_validate_meta_proposal_rejects_forbidden_layer():
    spec = load_meta_spec(ROOT)
    proposal = {
        "run_id": "r1",
        "changes": [{"layer": "unknown_layer", "target": "x", "rationale": "x", "evidence": []}],
    }
    result = validate_meta_proposal(proposal, spec)
    assert result["ok"] is False
    assert any("forbidden" in i for i in result["issues"])


def test_validate_meta_proposal_graph_spec_requires_human():
    spec = load_meta_spec(ROOT)
    proposal = {
        "run_id": "r1",
        "changes": [
            {
                "layer": "graph_spec",
                "target": "registry/graph_flow_spec.yaml",
                "rationale": "add meta edge",
                "evidence": ["stalemate"],
            }
        ],
    }
    result = validate_meta_proposal(proposal, spec)
    assert result["ok"] is False
    assert any("human" in i for i in result["issues"])


def test_validate_meta_proposal_ok_with_human_approval():
    spec = load_meta_spec(ROOT)
    proposal = {
        "run_id": "r1",
        "changes": [
            {
                "layer": "ops",
                "target": "ops/simulation/gpio_ext.py",
                "rationale": "parity fix",
                "evidence": ["delta.parity_ok"],
                "approval": "human_or_review",
            }
        ],
    }
    result = validate_meta_proposal(proposal, spec)
    assert result["ok"] is True


def test_queue_meta_proposal_writes_project_and_run_artifacts(tmp_path: Path):
    project_dir = tmp_path / "EXAMPLE-SOC"
    run_dir = project_dir / "runs" / "run-q1"
    run_dir.mkdir(parents=True)
    proposal = {
        "run_id": "run-q1",
        "changes": [
            {
                "layer": "md",
                "target": "verification/simulation/gpio_ext/CHECK.md",
                "rationale": "clarify step",
                "evidence": ["improvement_index"],
                "approval": "human_or_review",
            }
        ],
    }
    validation = validate_meta_proposal(proposal, load_meta_spec(ROOT))
    outcome = queue_meta_proposal(project_dir, run_dir, proposal, validation)
    assert outcome["queued"] is True
    assert (project_dir / "meta_proposals" / "run-q1.json").is_file()
    assert (run_dir / META_QUEUE_NAME).is_file()


def test_build_meta_collect_payload_change_hints_on_parity_fail():
    run_dir = EXAMPLE / "runs" / f"meta-col-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    signals = {
        "run_id": run_dir.name,
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "FAIL",
        "parity_ok": False,
        "stalemate": False,
        "llm_node_count": 2,
        "error_kind": "verification",
    }
    snapshot = {"improvement_index": 0.4, "delta_vs_previous": {"parity_ok": -1.0}}
    payload = build_meta_collect_payload(
        root=ROOT,
        project_dir=EXAMPLE,
        run_dir=run_dir,
        signals=signals,
        snapshot=snapshot,
        state={},
    )
    write_meta_collect_prompt(run_dir, payload)
    layers = {h["layer"] for h in payload["change_hints"]}
    assert "ops" in layers or "md" in layers
    assert (run_dir / "meta_collect_prompt.json").is_file()


def test_mechanical_meta_proposal_queues(tmp_path: Path):
    project_dir = tmp_path / "EXAMPLE-SOC"
    run_dir = project_dir / "runs" / "run-mech"
    run_dir.mkdir(parents=True)
    path, validation = write_mechanical_meta_proposal(
        run_dir,
        run_id="run-mech",
        stage="simulation",
        group="gpio_ext",
        root=ROOT,
    )
    assert path.is_file()
    assert validation["ok"] is True
    outcome = ensure_meta_queue_artifact(project_dir, run_dir, root=ROOT)
    assert (run_dir / META_QUEUE_NAME).is_file()
    assert outcome["queued"] is True
    assert outcome["status"] == "queued"


def test_write_empty_meta_proposal_satisfies_exit_contract(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_empty_meta_proposal(run_dir, run_id="r-stub", reason="stub")
    assert (run_dir / META_PROPOSAL_NAME).is_file()
    data = json.loads((run_dir / META_PROPOSAL_NAME).read_text())
    assert data["changes"] == []


def test_graph_flow_spec_allows_finalize_to_meta_collect():
    result = validate_transition(ROOT, "verify_group", "finalize", "meta_collect")
    assert result.ok is True


def test_graph_flow_spec_meta_chain_edges():
    from soc_verify.graph_spec import load_flow_spec

    spec = load_flow_spec(ROOT)
    vg = (spec.get("graphs") or {}).get("verify_group", {})
    nodes = vg.get("nodes") or {}
    edges = vg.get("edges") or {}
    for node in ("meta_collect", "meta_score", "meta_propose", "meta_queue"):
        assert node in nodes
    assert edges.get("finalize") == ["meta_collect"]
    assert edges.get("meta_propose") == ["meta_queue"]