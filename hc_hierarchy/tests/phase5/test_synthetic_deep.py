"""Validation on copied synthetic_deep_rtl (rvast demo_data)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN = ROOT / "design" / "synthetic_deep_rtl"
QUICK = SYN / "quick.hc.f"
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate" / "filelist.f"


@pytest.mark.requires_engine
def test_synthetic_quick_ingest_module_count():
    from hch.ingest.ingest import ingest_filelist

    if not QUICK.exists():
        pytest.skip(f"missing {QUICK}")
    mods = ingest_filelist(QUICK)
    assert len(mods) >= 50, f"expected many modules from u_ecc subtree, got {len(mods)}"


@pytest.mark.requires_engine
@pytest.mark.slow
def test_synthetic_full_filelist_sources_and_index(tmp_path):
    from hch.ingest.filelist import parse_filelist_simple
    from hch.index.batched_loader import build_index_batched

    full_fl = SYN / "top_deep_soc.hc.f"
    if not full_fl.exists():
        pytest.skip(f"missing {full_fl}")
    fl = parse_filelist_simple(str(full_fl))
    assert len(fl.source_files) >= 900, (
        f"expected 900+ source paths, got {len(fl.source_files)} errors={fl.errors[:3]}"
    )
    db = tmp_path / "full.hch.db"
    store = build_index_batched(
        str(full_fl),
        str(db),
        top_module="deep_soc_top",
        batch_size=64,
        force=True,
    )
    n_mod = store.count_modules()
    store.close()
    # Many .v files reuse the same module type names (thermal_sensor, etc.)
    assert n_mod >= 50, f"unique module defs, got {n_mod}"


@pytest.mark.requires_engine
def test_deep_soc_top_has_instances():
    from hch.ingest.ingest import ingest_source_files

    top = SYN / "rtl" / "deep_soc_top.v"
    if not top.exists():
        pytest.skip("deep_soc_top missing")
    mods = ingest_source_files(
        [top],
        include_dirs=[str(SYN / "common_inc"), str(SYN)],
    )
    assert "deep_soc_top" in mods
    assert len(mods["deep_soc_top"].instances) >= 5


@pytest.mark.requires_engine
def test_gen_ifdef_elaborate_generate_paths(tmp_path):
    from hch.index.loader import build_index_from_filelist

    if not GEN.exists():
        pytest.skip("gen_ifdef fixture missing")
    db = tmp_path / "gen.hch.db"
    store = build_index_from_filelist(
        str(GEN), str(db), top_module="top_soc", elaborate=True
    )
    n = store.count_instances()
    store.close()
    assert n >= 3
    import sqlite3

    conn = sqlite3.connect(db)
    paths = [r[0] for r in conn.execute("SELECT full_path FROM instances").fetchall()]
    conn.close()
    assert any("gen_loop" in p for p in paths)
    assert any("u_alt" in p for p in paths)