"""Path-walk module DB: tier-0 regex + tier-1 validated scan."""

from __future__ import annotations

from pathlib import Path

from scan_inst.filelist import parse_filelist
from scan_inst.index import DesignIndex
from scan_inst.path_walk import create_path_walk_index, run_path_walk_connect
from scan_inst.path_walk_db import PathWalkModuleDb, path_walk_db_cache_key


def _write_dup_module_design(tmp_path: Path) -> tuple[Path, Path]:
    """Same module name in two files; only second has the child instance."""
    wrong = tmp_path / "parent_wrong.v"
    wrong.write_text(
        """
        module parent;
          // no children — wrong decl file for tier-0 hit
        endmodule
        """,
        encoding="utf-8",
    )
    right = tmp_path / "parent_right.v"
    right.write_text(
        """
        module child(input in, output out);
          assign out = in;
        endmodule

        module parent;
          child u_child (.in(1'b0), .out());
        endmodule
        """,
        encoding="utf-8",
    )
    top = tmp_path / "top.v"
    top.write_text(
        """
        module parent;
          // stub in top file — tier-0 will list parent here too
        endmodule

        module top;
          parent u_parent();
        endmodule
        """,
        encoding="utf-8",
    )
    fl = tmp_path / "filelist.f"
    fl.write_text(
        "\n".join(
            str(p.resolve())
            for p in (wrong, right, top)
        )
        + "\n",
        encoding="utf-8",
    )
    return fl, right


def _write_ifdef_module_design(tmp_path: Path) -> Path:
    rtl = tmp_path / "ifdef_top.v"
    rtl.write_text(
        """
        `define USE_CHILD

        module child(input in, output out);
          assign out = in;
        endmodule

        `ifdef USE_CHILD
        module parent;
          child u_child (.in(1'b0), .out());
        endmodule
        `else
        module parent;
        endmodule
        `endif

        module top;
          parent u_parent();
        endmodule
        """,
        encoding="utf-8",
    )
    fl = tmp_path / "filelist.f"
    fl.write_text(str(rtl.resolve()) + "\n", encoding="utf-8")
    return fl


def test_tier1_picks_file_with_expected_instance(tmp_path: Path):
    fl_path, right_file = _write_dup_module_design(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    index, mod_db = create_path_walk_index(fl, "top", defines={})
    assert mod_db.ensure_module_in_index(
        "parent",
        expect_inst=("parent", "u_child"),
    )
    rec = index.get_module("parent")
    assert rec is not None
    assert str(Path(rec.file_path).resolve()) == str(right_file.resolve())


def test_path_walk_db_disk_cache_reuse(tmp_path: Path):
    fl_path = _write_ifdef_module_design(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    cache_dir = tmp_path / "pw-cache"
    cache_key = path_walk_db_cache_key(
        [str(p) for p in fl.source_files],
        defines=dict(fl.defines),
        include_dirs=[str(p) for p in fl.include_dirs],
    )

    index = DesignIndex._assemble(
        {},
        path_patterns=[],
        module_patterns=[],
        preprocess_include_dirs=[str(p) for p in fl.include_dirs],
        preprocess_defines=dict(fl.defines),
    )
    db1 = PathWalkModuleDb(
        [str(p) for p in fl.source_files],
        index,
        include_dirs=[str(p) for p in fl.include_dirs],
        defines=dict(fl.defines),
        cache_dir=cache_dir,
        cache_key=cache_key,
    )
    db1.tier1_scan_file(str(fl.source_files[0]))
    assert db1.files_validated == 1
    assert db1.cache_validated_hits == 0

    index2 = DesignIndex._assemble(
        {},
        path_patterns=[],
        module_patterns=[],
        preprocess_include_dirs=[str(p) for p in fl.include_dirs],
        preprocess_defines=dict(fl.defines),
    )
    db2 = PathWalkModuleDb(
        [str(p) for p in fl.source_files],
        index2,
        include_dirs=[str(p) for p in fl.include_dirs],
        defines=dict(fl.defines),
        cache_dir=cache_dir,
        cache_key=cache_key,
    )
    db2.tier1_scan_file(str(fl.source_files[0]))
    assert db2.cache_validated_hits == 1
    assert db2.files_validated == 1


def test_path_walk_walks_through_dup_module_files(tmp_path: Path):
    fl_path, _right = _write_dup_module_design(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest

    request = ConnectivityRequest(
        checks=(ConnectivityCheck("top.u_parent.u_child.in", "top.u_parent.u_child.in"),),
        top="top",
    )
    batch, index, state = run_path_walk_connect(
        request,
        fl,
        top="top",
        no_cache=True,
    )
    assert "top.u_parent.u_child" in state.rows_by_path
    assert batch.results[0].connected is True
    assert index.get_module("child") is not None