"""Run profile — training vs production graph behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.config import load_policies

VALID_PROFILES = frozenset({"training", "production", "held_out"})


def resolve_run_profile_name(root: Path, explicit: str | None = None) -> str:
    """Return validated profile name; explicit wins over policies default."""
    if explicit and explicit in VALID_PROFILES:
        return explicit
    policies = load_policies(root)
    profiles = policies.get("profiles") or {}
    default = str(profiles.get("default") or "production")
    if default not in VALID_PROFILES:
        default = "production"
    return default


def load_run_profile(root: Path, name: str | None = None) -> dict[str, Any]:
    """Load named profile config merged with resolved name."""
    policies = load_policies(root)
    profiles = policies.get("profiles") or {}
    profile_name = resolve_run_profile_name(root, name)
    profile_body = profiles.get(profile_name)
    if not isinstance(profile_body, dict):
        profile_body = {}
    return {"name": profile_name, **profile_body}


def should_skip_meta_after_finalize(root: Path, profile_name: str | None = None) -> bool:
    profile = load_run_profile(root, profile_name)
    return bool(profile.get("skip_meta_after_finalize"))


def should_auto_apply_node_guides(root: Path, profile_name: str | None = None) -> bool:
    profile = load_run_profile(root, profile_name)
    return bool(profile.get("auto_apply_node_guides"))


def profile_requires_held_out(root: Path, profile_name: str | None = None) -> bool:
    profile = load_run_profile(root, profile_name)
    return bool(profile.get("require_held_out"))