"""Path-walk per-node rtl + filelist trace logging."""

from __future__ import annotations

import io
from pathlib import Path

from scan_inst.filelist import parse_filelist
from scan_inst.hierarchy_log import format_path_walk_spine_lines
from scan_inst.models import FlatRow
from scan_inst.path_walk import build_path_walk_state_from_specs


def _row(path: str, *, file: str, via: str, chain: str) -> FlatRow:
    parts = path.split(".")
    return FlatRow(
        full_path=path,
        inst_leaf=parts[-1],
        module=parts[-1],
        depth=len(parts) - 1,
        parent_path=".".join(parts[:-1]) if len(parts) > 1 else None,
        file=file,
        via_filelist=via,
        filelist_chain=chain,
    )


def test_path_walk_spine_lines_include_filelist():
    rows = {
        "top": _row("top", file="/rtl/top.v", via="/lists/a.f", chain="/lists/a.f"),
        "top.u_mid": _row(
            "top.u_mid",
            file="/rtl/mid.v",
            via="/lists/b.f",
            chain="/lists/a.f > /lists/b.f",
        ),
    }
    lines = format_path_walk_spine_lines("top.u_mid", rows)
    joined = "\n".join(lines)
    assert "rtl=/rtl/top.v" in joined
    assert "via_filelist=/lists/a.f" in joined
    assert "rtl=/rtl/mid.v" in joined
    assert "filelist_chain=/lists/a.f > /lists/b.f" in joined


def test_path_walk_trace_logs_nodes_and_miss(tmp_path: Path):
    top_v = tmp_path / "top.v"
    top_v.write_text(
        """
        module top;
          // no children
        endmodule
        """,
        encoding="utf-8",
    )
    fl_path = tmp_path / "design.f"
    fl_path.write_text(f"{top_v.resolve()}\n", encoding="utf-8")
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    listing = str(fl_path.resolve())
    from scan_inst.path_walk import create_path_walk_index

    index, mod_db = create_path_walk_index(fl, "top", defines={})
    buf = io.StringIO()
    build_path_walk_state_from_specs(
        index,
        "top",
        ["top.u_missing"],
        mod_db,
        trace_stream=buf,
    )
    text = buf.getvalue()
    assert "[scan-inst path-walk]" in text
    assert "walk target=top.u_missing" in text
    assert "ok top" in text
    assert "rtl=" in text
    assert "via_filelist=" in text
    assert "miss inst=u_missing under top" in text
    assert "walked" in text


def test_path_walk_trace_writes_run_log(tmp_path: Path):
    top_v = tmp_path / "top.v"
    top_v.write_text(
        """
        module top;
        endmodule
        """,
        encoding="utf-8",
    )
    fl_path = tmp_path / "design.f"
    fl_path.write_text(f"{top_v.resolve()}\n", encoding="utf-8")
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    from scan_inst.path_walk import create_path_walk_index

    index, mod_db = create_path_walk_index(fl, "top", defines={})
    log_path = tmp_path / "out.tsv.scan-inst.log"
    build_path_walk_state_from_specs(
        index,
        "top",
        ["top.u_missing"],
        mod_db,
        trace_log_path=log_path,
    )
    text = log_path.read_text(encoding="utf-8")
    assert "# path-walk trace" in text
    assert "[scan-inst path-walk]" in text
    assert "ok top" in text
    assert "rtl=" in text
    assert "via_filelist=" in text