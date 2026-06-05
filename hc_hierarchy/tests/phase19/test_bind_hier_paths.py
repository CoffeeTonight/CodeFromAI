"""Phase 19: bind hierarchical target in flat paths."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_bind_under_instance_anchor():
    from hch.index.loader import build_index_from_filelist

    fl = ROOT / "design" / "extras" / "parse_bind" / "filelist.f"
    # filelist may not include bind_hier — index inline
    rtl = ROOT / "design" / "extras" / "parse_bind" / "rtl"
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".f", delete=False) as tf:
        tf.write(f"{rtl}/top_bind_cu.v\n{rtl}/bind_hier.v\n")
        flist = tf.name
    db = Path(flist).parent / "bind_hier.hch.db"
    store = build_index_from_filelist(flist, str(db), top_module="top")
    paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert any("u_sub" in p and "u_bind" in p for p in paths)