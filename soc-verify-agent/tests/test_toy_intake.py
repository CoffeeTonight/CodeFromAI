"""toy_intake — resolve and slug."""

from __future__ import annotations

from pathlib import Path

import pytest

from soc_verify.toy_intake import resolve_toy_intake, slug_toy_project_id

ROOT = Path(__file__).resolve().parents[1]


def test_slug_toy_project_id():
    assert slug_toy_project_id("VERIF-CPU-SOC") == "TOY-VERIFCPU"
    assert slug_toy_project_id("VERIF-CPU-SOC", "MY-TOY") == "MY-TOY"


def test_resolve_from_verif_cpu_snapshot():
    spec = resolve_toy_intake(ROOT, source_id="VERIF-CPU-SOC")
    assert spec.source_id == "VERIF-CPU-SOC"
    assert spec.local_clone_path
    assert (spec.resolved_rtl_root() / spec.root_marker).is_file()


def test_resolve_missing_raises():
    with pytest.raises(FileNotFoundError):
        resolve_toy_intake(ROOT, source_id="NO-SUCH-PROJECT")