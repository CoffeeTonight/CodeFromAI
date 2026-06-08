"""Smoke tests for rvast package (Python-only core)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_dql_matches_tiny_soc():
    from rvast.dql import query_dql
    from rvast.schema import instances_from_json

    data = instances_from_json(ROOT / "demo_data/tiny_soc.json")
    rows = [d.to_dict() for d in data]
    hits = query_dql('module ~ "uart"', rows)
    assert len(hits) >= 2


def test_pipeline_design_filelist():
    from rvast.pipeline import run_from_filelist

    fl = ROOT / "design/HDLforAST/filelist.f"
    if not fl.exists():
        pytest.skip("design filelist missing")
    result = run_from_filelist(str(fl))
    assert result.mode_used in ("hierarchy", "propagator", "none")
    # Small design should yield at least one instance when hierarchy mode works
    if result.mode_used == "hierarchy":
        assert len(result.instances) >= 1
        by_name = {i.name: i for i in result.instances}
        mid = by_name.get("top_a.u_middle_0")
        if mid:
            assert mid.module == "middle_module"
            assert "clk" in mid.ports