"""B7 variant rows + from_macro DQL on inst_tags_json."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN_SOC = ROOT / "design" / "extras" / "gen_ifdef_generate"
MACRO = ROOT / "design" / "extras" / "macro_hierarchy"


@pytest.mark.skipif(not (GEN_SOC / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_multi_variant_single_db(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore
    from hch.index.variant_index import compare_variant_paths

    db = tmp_path / "variants.hch.db"
    store = build_index_from_filelist(
        str(GEN_SOC / "filelist.f"),
        str(db),
        top_module="top_soc",
        index_cwd=GEN_SOC,
        variants=[
            ("base", {"USE_ALT": "0"}),
            ("alt", {"USE_ALT": "1"}),
        ],
    )
    assert store.get_meta("tier_contract_version") == "1"
    assert store.get_meta("ifdef_variant_mode") == "multi_row"
    n_base = store.conn.execute(
        "SELECT COUNT(*) FROM instances WHERE variant='base'"
    ).fetchone()[0]
    n_alt = store.conn.execute(
        "SELECT COUNT(*) FROM instances WHERE variant='alt'"
    ).fetchone()[0]
    diff = compare_variant_paths(store, "base", "alt")
    base_paths = {
        r[0]
        for r in store.conn.execute(
            "SELECT full_path FROM instances WHERE variant='base'"
        ).fetchall()
    }
    alt_paths = {
        r[0]
        for r in store.conn.execute(
            "SELECT full_path FROM instances WHERE variant='alt'"
        ).fetchall()
    }
    store.close()
    assert n_base > 0 and n_alt > 0
    assert diff["only_a"] or diff["only_b"]
    assert any("u_default" in p for p in base_paths)
    assert any("u_alt" in p for p in alt_paths)


@pytest.mark.skipif(not (MACRO / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_dql_from_macro_tag(tmp_path):
    import sqlite3

    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore
    from hch.query.dql.sql_compiler import plan_dql

    db = tmp_path / "macro_dql.hch.db"
    build_index_from_filelist(
        str(MACRO / "filelist.f"),
        str(db),
        top_module="top_macro",
        index_cwd=MACRO,
    )
    store = HierarchyStore(str(db))
    plan = plan_dql('from_macro = "1"')
    store.conn.row_factory = sqlite3.Row
    hits = store.conn.execute(plan.sql, plan.params).fetchall()
    store.close()
    assert len(hits) >= 2