"""Tests for VERIF-CPU-SOC intake_resolve (RTL_ROOT + gate crystallize)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "projects" / "VERIF-CPU-SOC"
sys.path.insert(0, str(PROJECT))

from ops.intake_resolve import (  # noqa: E402
    crystallize_coi_conn_checks,
    crystallize_slave_rw_scenarios,
    resolve_rtl_root,
)


def test_resolve_rtl_root_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_rtl = tmp_path / "rtl"
    fake_rtl.mkdir()
    (fake_rtl / "example.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    tag = "t1"
    deploy = tmp_path / "proj" / "inputs" / "tags" / tag / "deployment"
    deploy.mkdir(parents=True)
    intake = deploy / "customer_soc_intake.yaml"
    intake.write_text(
        "rtl:\n  rtl_root_override: " + str(fake_rtl) + "\n",
        encoding="utf-8",
    )
    proj = tmp_path / "proj"
    (proj / "cache.yaml").write_text("tag:\n  value: t1\nclone:\n  path: /nonexistent\n", encoding="utf-8")
    (proj / "discovered.yaml").write_text("rtl_subdir: VerifCPU/verif_cpu_verilog\n", encoding="utf-8")

    assert resolve_rtl_root(proj, tag=tag) == fake_rtl.resolve()


def test_crystallize_coi_conn_checks(tmp_path: Path):
    tag = "main"
    proj = tmp_path / "proj"
    deploy = proj / "inputs" / "tags" / tag / "deployment"
    deploy.mkdir(parents=True)
    (proj / "cache.yaml").write_text("tag:\n  value: main\n", encoding="utf-8")
    (deploy / "customer_soc_intake.yaml").write_text(
        """
chip:
  name: my_soc
rtl:
  customer_top: tb/chip_top_example.v
  filelist: filelists/eda/test/chip_top_example/manifest.list
""".strip(),
        encoding="utf-8",
    )

    out = crystallize_coi_conn_checks(proj, tag=tag)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["top"] == "chip_top_example"
    assert data["checks"][0]["a"].startswith("chip_top_example.")


def test_crystallize_slave_rw_scenarios():
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    from soc_verify.models import load_yaml

    out = crystallize_slave_rw_scenarios(
        PROJECT, tag="main", intake_data=load_yaml(example) or {}
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source"] == "crystallize_from_intake"
    assert data["integration"]["top"] == "chip_top_example"
    assert data["integration_smoke"]["command"]
    sim_single = next(t for t in data["tiers"] if t["id"] == "sim_single")
    assert len(sim_single["slaves"]) == 3
    assert "chip_top_example: PASS" in sim_single["optional_chip_top"]["success_markers"]