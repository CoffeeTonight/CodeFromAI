"""Batch DQL verification on dummy designs (HDLforAST + synthetic quick)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
from hch.paths import design_dir

HDL_FL = design_dir("HDLforAST") / "filelist.f"
QUICK_FL = ROOT / "design" / "synthetic_deep_rtl" / "quick.hc.f"
BATCH_HDL = ROOT / "fixtures" / "dql_batch_hdlforast.txt"
BATCH_QUICK = ROOT / "fixtures" / "dql_batch_synthetic_quick.txt"
FULL_FL = ROOT / "design" / "synthetic_deep_rtl" / "top_deep_soc.hc.f"
BATCH_FULL = ROOT / "fixtures" / "dql_batch_synthetic_full.txt"


def _run_batch(db: Path, batch_file: Path) -> dict[str, int]:
    import sqlite3

    from hch.query.dql.planner import apply_post_filters, plan_dql

    lines = [
        ln.strip()
        for ln in batch_file.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    for q in lines:
        plan = plan_dql(q)
        rows = [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()]
        rows = apply_post_filters(rows, plan)
        counts[q] = len(rows)
    conn.close()
    return counts


@pytest.mark.requires_engine
def test_batch_hdlforast_golden(tmp_path):
    from hch.index.loader import build_index_from_filelist

    if not HDL_FL.exists():
        pytest.skip(f"missing {HDL_FL}")
    if not BATCH_HDL.exists():
        pytest.skip("batch fixture missing")

    db = tmp_path / "hdl.hch.db"
    store = build_index_from_filelist(str(HDL_FL), str(db), top_module="top_module")
    store.close()

    c = _run_batch(db, BATCH_HDL)

    assert c['path = "top_module"'] >= 1
    assert c['path ^= "top_module.u_middle_0"'] >= 1
    assert c['module ~ "middle*"'] >= 1
    assert c['port ~ "clk" AND path ^= "top_module"'] >= 1
    assert c['(module ~ "middle*" OR module ~ "sub_*") AND path ^= "top_module"'] >= 2
    assert c['node_count == 1 AND path ^= "top_module"'] >= 1
    assert c['lastnode AND path ^= "top_module"'] >= 1


@pytest.mark.requires_engine
def test_batch_synthetic_quick_golden(tmp_path):
    from hch.index.loader import build_index_from_filelist

    if not QUICK_FL.exists():
        pytest.skip(f"missing {QUICK_FL}")
    if not BATCH_QUICK.exists():
        pytest.skip("batch fixture missing")

    db = tmp_path / "quick.hch.db"
    store = build_index_from_filelist(
        str(QUICK_FL), str(db), top_module="deep_soc_top"
    )
    n = store.count_instances()
    store.close()
    assert n >= 5, f"expected hierarchy instances, got {n}"

    c = _run_batch(db, BATCH_QUICK)

    assert c['path = "deep_soc_top"'] >= 1
    assert c['path ^= "deep_soc_top.u_"'] >= 1
    assert c['module ~ "jupiter*"'] >= 1
    assert c['module ~ "ecc*"'] >= 1


@pytest.mark.requires_engine
@pytest.mark.slow
def test_batch_synthetic_full_golden(tmp_path):
    from hch.index.batched_loader import build_index_batched

    if not FULL_FL.exists():
        pytest.skip(f"missing {FULL_FL}")
    if not BATCH_FULL.exists():
        pytest.skip("full batch fixture missing")

    db = tmp_path / "full.hch.db"
    store = build_index_batched(
        str(FULL_FL),
        str(db),
        top_module="deep_soc_top",
        batch_size=64,
        force=True,
    )
    n_inst = store.count_instances()
    n_mod = store.count_modules()
    store.close()
    assert n_mod >= 50, f"unique modules, got {n_mod}"
    assert n_inst >= 500, f"deep path flatten expected, got {n_inst}"

    c = _run_batch(db, BATCH_FULL)

    assert c['path = "deep_soc_top"'] >= 1
    assert c['path ^= "deep_soc_top.u_"'] >= 100
    assert c['module ~ "jupiter*"'] >= 1
    assert c['module ~ "ecc*"'] >= 1
    assert c['module IN ("jupiter_noc", "nvme_host", "pmu")'] >= 2
    assert c['port ~ "clk"'] >= 1
    assert c['node_count == 1 AND path ^= "deep_soc_top"'] >= 1
    assert c['port ~ "clk"'] >= 1