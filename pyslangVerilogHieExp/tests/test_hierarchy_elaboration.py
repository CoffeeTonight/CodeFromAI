"""Tests for Verilog parse + hierarchy elaboration field correctness."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "design/HDLforAST"


def test_parse_nonansi_and_ansi_ports():
    from rvast.parse.verilog import parse_file_to_json

    mid = parse_file_to_json(str(DESIGN / "middle_module.v"), "/tmp/rvast_ports")
    mm = mid["instances"]["middle_module"]
    assert set(mm["ports"].keys()) >= {"clk", "reset", "out"}

    sub = parse_file_to_json(str(DESIGN / "sub_module.v"), "/tmp/rvast_ports")
    sm = sub["instances"]["sub_module"]
    assert set(sm["ports"].keys()) == {"clk", "reset", "out"}


def test_elaboration_preserves_module_type_and_ports():
    from rvast.pipeline import run_from_filelist, PipelineConfig, ElabMode

    fl = DESIGN / "filelist.f"
    if not fl.exists():
        pytest.skip("design filelist missing")

    result = run_from_filelist(
        str(fl),
        config=PipelineConfig(mode=ElabMode.HIERARCHY, clean_work=False),
    )
    assert result.mode_used == "hierarchy"
    by_name = {i.name: i for i in result.instances}

    mid = by_name.get("top_a.u_middle_0")
    assert mid is not None, "expected top_a.u_middle_0"
    assert mid.module == "middle_module"
    assert set(mid.ports) >= {"clk", "reset", "out"}

    sub = by_name.get("top_a.u_middle_0.u_subTop_0")
    assert sub is not None
    assert sub.module == "sub_module"
    assert set(sub.ports) == {"clk", "reset", "out"}

    assert mid.file.endswith("middle_module.v") or "middle_module" in mid.file


def test_init_module_no_module_keyword_collision():
    from rvast.parse.verilog import VerilogParser

    mod = VerilogParser(type("F", (), {"hdls": {}})(), "/tmp").init_module()
    assert "module" not in mod or mod.get("module") != "module"
    assert mod.get("kind") == "module"