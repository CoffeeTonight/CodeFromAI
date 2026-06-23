"""Regression tests for Claude improvement guidelines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soc_verify.completeness import CompletenessMetrics, evaluate_completeness_policy
from soc_verify.config import load_policies
from soc_verify.loop_guard import detect_stagnation_pattern, record_transition
from soc_verify.meta_graph import (
    NEVER_AUTO_APPLY_LAYERS,
    apply_low_risk_artifacts,
    layer_auto_apply_allowed,
    load_meta_spec,
)
from soc_verify.models import save_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_completeness_score_ignores_i_multiplier():
    """info_unresolved flag does not zero the continuous C product."""
    clean = CompletenessMetrics.from_events({"gates_run": 5, "info_interrupts": 0})
    flagged = CompletenessMetrics.from_events({"gates_run": 5, "info_interrupts": 1})
    assert clean.score == pytest.approx((1 - clean.e) * (1 - clean.t) * (1 - clean.l))
    assert flagged.i == 1.0
    assert flagged.score == clean.score


def test_info_unresolved_blocks_via_policy_not_multiplier():
    policies = load_policies(ROOT)
    metrics = CompletenessMetrics.from_events({"gates_run": 5, "info_interrupts": 1})
    decision = evaluate_completeness_policy(
        metrics, policies, verdict="PASS", trust_score=0.9, trust_runs=10
    )
    assert decision.promote_allowed is False
    assert decision.promote_reason == "info_unresolved"
    assert decision.continue_improvement is True


def test_first_pass_requires_min_gates_before_parity_exit():
    policies = load_policies(ROOT)
    metrics = CompletenessMetrics.from_events({"gates_run": 1})
    decision = evaluate_completeness_policy(
        metrics, policies, verdict="PASS", trust_score=0.9, trust_runs=10
    )
    assert decision.continue_improvement is True
    assert decision.promote_allowed is False
    assert "min_gates" in decision.promote_reason


def test_first_pass_requires_min_trust_runs():
    policies = load_policies(ROOT)
    metrics = CompletenessMetrics.from_events({"gates_run": 5})
    decision = evaluate_completeness_policy(
        metrics, policies, verdict="PASS", trust_score=0.9, trust_runs=1
    )
    assert decision.continue_improvement is True
    assert "min_trust_runs" in decision.promote_reason


def test_hardened_pass_allows_promote_when_thresholds_met():
    policies = load_policies(ROOT)
    metrics = CompletenessMetrics.from_events({"gates_run": 5})
    decision = evaluate_completeness_policy(
        metrics, policies, verdict="PASS", trust_score=0.9, trust_runs=5
    )
    assert decision.continue_improvement is False
    assert decision.promote_allowed is True


def test_oscillation_detects_three_cycle_pattern():
    t = [
        "run_gate:verification",
        "diagnose_env:env",
        "patch_bridge:env",
        "run_gate:verification",
        "diagnose_env:env",
        "patch_bridge:env",
    ]
    assert detect_stagnation_pattern(t) == "OSCILLATION"


def test_graph_source_never_auto_apply_enforced(tmp_path: Path):
    spec = load_meta_spec(ROOT)
    hacked = dict(spec)
    hacked["layers"] = dict(spec.get("layers") or {})
    hacked["layers"]["graph_source"] = {
        **hacked["layers"]["graph_source"],
        "auto_apply": True,
    }
    project = tmp_path / "SOC"
    project.mkdir()
    proposal = {
        "run_id": "r1",
        "changes": [
            {
                "layer": "graph_source",
                "target": "src/soc_verify/graphs/verify_group.py",
                "content": "# evil",
                "rationale": "test",
                "evidence": ["x"],
                "approval": "human_required",
            }
        ],
    }
    policies = load_policies(ROOT)
    out = apply_low_risk_artifacts(project, proposal, hacked, policies=policies)
    assert out["applied"] == []
    assert any("never_auto_apply_layer" in s for s in out["skipped"])


def test_never_auto_apply_layers_constant():
    assert "graph_source" in NEVER_AUTO_APPLY_LAYERS
    assert layer_auto_apply_allowed(
        "graph_source",
        layer_spec={"auto_apply": True},
        policies={"meta_graph": {"graph_source_never_auto_apply": True}},
    ) == (False, "never_auto_apply_layer")