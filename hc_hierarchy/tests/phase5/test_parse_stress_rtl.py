"""multihost_peri_soc parse-eval: generate, ifdef, param chain, include-only."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "multihost_peri_soc"
FULL_FL = DESIGN / "orion_soc.f"


@pytest.fixture(scope="module")
def orion_env():
    import os

    if not (DESIGN / "rtl" / "top" / "orion_soc_top.v").exists():
        pytest.skip("run: python3 design/multihost_peri_soc/scripts/generate_rtl.py")
    os.environ["ORION_RTL_ROOT"] = str(DESIGN.resolve())
    return {"ORION_RTL_ROOT": str(DESIGN.resolve())}


@pytest.mark.requires_engine
def test_filelist_excludes_include_only_rtl(orion_env):
    from hch.ingest.filelist import parse_filelist_simple

    fl = parse_filelist_simple(str(FULL_FL), env=orion_env)
    names = {p.name for p in fl.source_files}
    assert "include_only_mod.v" not in names
    assert "param_leaf.v" not in names
    assert "stress_generate.v" in names


@pytest.mark.requires_engine
def test_parse_stress_modules_and_generate(orion_env):
    from hch.ingest.ingest import ingest_filelist
    from hch.ingest.hierarchy_build import elaborate_flat

    mods = ingest_filelist(str(FULL_FL), env=orion_env)
    assert "include_only_mod" in mods
    assert "param_leaf" in mods
    assert "stress_generate" in mods

    ig = mods["include_gateway"]
    assert any(e.child_module == "include_only_mod" for e in ig.instances)

    gen = mods["stress_generate"]
    insts = {e.inst_name for e in gen.instances}
    assert "u_uart_gen" in insts or "u_spi_gen" in insts

    chain = mods["param_stack_l1"]
    assert chain.instances[0].child_module == "param_leaf"

    flat = elaborate_flat(mods, top_module="orion_soc_top")
    deep = [f for f in flat if "u_param" in f.full_path and "param_stack" in f.module]
    assert len(deep) >= 5


@pytest.mark.requires_engine
def test_ifdef_branch_changes_with_define(orion_env):
    from hch.ingest.ingest import ingest_source_files

    v = DESIGN / "rtl" / "stress" / "stress_ifdef_nest.v"
    inc = [
        str(DESIGN / "include" / "common"),
        str(DESIGN / "include" / "peri"),
    ]
    base_def = {"ORION_SOC": "1", "ENABLE_I3C": "1"}
    mods_i3c = ingest_source_files(
        [v], include_dirs=inc, defines={**base_def, "SIM_SPEEDUP": "1"}
    )
    mods_spi = ingest_source_files(
        [v],
        include_dirs=inc,
        defines={**base_def, "ENABLE_SPI_SLAVE": "1"},
    )
    i3c = {e.inst_name for e in mods_i3c["stress_ifdef_nest"].instances}
    spi = {e.inst_name for e in mods_spi["stress_ifdef_nest"].instances}
    assert "u_i3c_fast" in i3c
    assert "u_spi_slv" in spi
    assert i3c != spi