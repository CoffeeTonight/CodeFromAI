"""Shared path helpers for verify_group graph nodes."""

from __future__ import annotations

from pathlib import Path

from soc_verify.graphs.state import VerifyGroupState


def project_dir(state: VerifyGroupState) -> Path:
    return Path(state["project_dir"])


def run_dir(state: VerifyGroupState) -> Path:
    return project_dir(state) / "runs" / state["run_id"]