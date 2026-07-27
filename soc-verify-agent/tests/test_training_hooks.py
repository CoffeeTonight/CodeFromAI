"""Training hooks — node guide auto_apply."""

from __future__ import annotations

from pathlib import Path

from soc_verify.training_hooks import apply_training_node_guides

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "projects" / "MINI-SOC"


def test_apply_training_node_guides_disabled_for_production():
    out = apply_training_node_guides(ROOT, MINI, run_profile="production")
    assert out["applied"] is False


def test_apply_training_node_guides_runs_for_training():
    out = apply_training_node_guides(ROOT, MINI, run_profile="training")
    assert out["applied"] is True