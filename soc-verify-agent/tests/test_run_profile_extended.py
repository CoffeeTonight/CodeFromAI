"""Run profile — held_out split and training hooks flags."""

from __future__ import annotations

from pathlib import Path

from soc_verify.run_profile import (
    load_run_profile,
    profile_requires_held_out,
    should_auto_apply_node_guides,
)

ROOT = Path(__file__).resolve().parents[1]


def test_training_profile_flags():
    p = load_run_profile(ROOT, "training")
    assert p["skip_meta_after_finalize"] is True
    assert should_auto_apply_node_guides(ROOT, "training") is True
    assert profile_requires_held_out(ROOT, "training") is False


def test_held_out_profile_flags():
    p = load_run_profile(ROOT, "held_out")
    assert p["skip_meta_after_finalize"] is False
    assert profile_requires_held_out(ROOT, "held_out") is True
    assert should_auto_apply_node_guides(ROOT, "held_out") is False


def test_production_requires_held_out():
    assert profile_requires_held_out(ROOT, "production") is True