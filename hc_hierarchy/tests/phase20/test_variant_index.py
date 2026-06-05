"""Phase 20: multi-variant index in one DB."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.requires_engine
def test_two_variants_in_db(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "v.hch.db"
    store = build_index_from_filelist(
        str(GEN / "filelist.f"),
        str(db),
        top_module="top_soc",
        variants=[
            ("base", {"USE_ALT": ""}),
            ("alt", {"USE_ALT": "1"}),
        ],
        variant_compare=("base", "alt"),
    )
    variants = json.loads(store.get_meta("variants_json", "[]"))
    diff = json.loads(store.get_meta("variant_diff_json", "{}"))
    n_base = store.conn.execute(
        "SELECT COUNT(*) FROM instances WHERE variant='base'"
    ).fetchone()[0]
    n_alt = store.conn.execute(
        "SELECT COUNT(*) FROM instances WHERE variant='alt'"
    ).fetchone()[0]
    store.close()
    assert len(variants) == 2
    assert n_base > 0 and n_alt > 0
    assert diff.get("only_a") or diff.get("only_b")