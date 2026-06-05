"""multihost_peri_soc: rich peri/host/mem hierarchy + filelist."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "multihost_peri_soc"
QUICK_FL = DESIGN / "quick.f"


@pytest.fixture(scope="module")
def orion_env():
    import os

    os.environ["ORION_RTL_ROOT"] = str(DESIGN.resolve())
    return {"ORION_RTL_ROOT": str(DESIGN.resolve())}


@pytest.mark.requires_engine
def test_orion_filelist_parses_many_sources(orion_env):
    from hch.ingest.filelist import parse_filelist_simple

    if not QUICK_FL.exists():
        pytest.skip("run design/multihost_peri_soc/scripts/generate_rtl.py first")
    fl = parse_filelist_simple(str(QUICK_FL), env=orion_env)
    assert len(fl.source_files) >= 12
    assert "ORION_SOC" in fl.defines


@pytest.mark.requires_engine
def test_orion_hierarchy_depth_and_peri(orion_env, tmp_path):
    from hch.ingest.ingest import ingest_filelist
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.index.store import HierarchyStore
    from hch.query.dql.planner import plan_dql
    import sqlite3

    if not QUICK_FL.exists():
        pytest.skip("generate RTL first")

    mods = ingest_filelist(str(QUICK_FL), env=orion_env)
    flat = elaborate_flat(mods, top_module="orion_soc_top")
    assert len(flat) >= 30
    assert any("u_uart" in f.full_path for f in flat)
    assert any("u_spi" in f.full_path for f in flat)
    assert any(f.module == "ddr5_ctrl" for f in flat)

    db = tmp_path / "orion.hch.db"
    store = HierarchyStore(str(db))
    store.load_modules(mods.values())
    store.load_instances(flat)
    store.close()

    conn = sqlite3.connect(db)
    plan = plan_dql('inst ~ "u_i3c*"')
    n = len(conn.execute(plan.sql, plan.params).fetchall())
    conn.close()
    assert n >= 1