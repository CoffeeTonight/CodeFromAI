"""Run profile — training vs production policies."""

from __future__ import annotations

from pathlib import Path

from soc_verify.run_profile import (
    load_run_profile,
    resolve_run_profile_name,
    should_skip_meta_after_finalize,
)

ROOT = Path(__file__).resolve().parents[1]


def test_resolve_run_profile_defaults_to_production():
    assert resolve_run_profile_name(ROOT, None) == "production"
    assert resolve_run_profile_name(ROOT, "") == "production"


def test_resolve_run_profile_explicit_training():
    assert resolve_run_profile_name(ROOT, "training") == "training"


def test_load_run_profile_training_skips_meta():
    profile = load_run_profile(ROOT, "training")
    assert profile["name"] == "training"
    assert profile["skip_meta_after_finalize"] is True


def test_should_skip_meta_after_finalize_by_profile():
    assert should_skip_meta_after_finalize(ROOT, "training") is True
    assert should_skip_meta_after_finalize(ROOT, "production") is False