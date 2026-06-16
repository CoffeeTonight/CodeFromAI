"""Path-walk: A.B.C.D chain across separate RTL files + library stub trap."""

from __future__ import annotations

from pathlib import Path

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import run_path_walk_connect


def _write_abcd_design(tmp_path: Path, *, with_lib_stub: bool = False) -> Path:
    a_v = tmp_path / "a.v"
    a_v.write_text(
        """
        module A;
          B B ();
        endmodule
        """,
        encoding="utf-8",
    )
    b_v = tmp_path / "b.v"
    b_v.write_text(
        """
        module B;
          C C ();
        endmodule
        """,
        encoding="utf-8",
    )
    c_v = tmp_path / "c.v"
    c_v.write_text(
        """
        module C;
          D D ();
        endmodule
        """,
        encoding="utf-8",
    )
    d_v = tmp_path / "d.v"
    d_v.write_text(
        """
        module D;
        endmodule
        """,
        encoding="utf-8",
    )
    if with_lib_stub:
        lib = tmp_path / "lib_stub.v"
        lib.write_text(
            """
            module B;
            endmodule
            module C;
            endmodule
            """,
            encoding="utf-8",
        )
        fl = tmp_path / "design.f"
        fl.write_text(
            "\n".join(
                str(p.resolve())
                for p in (a_v, b_v, c_v, d_v)
            )
            + f"\n-v {lib.resolve()}\n",
            encoding="utf-8",
        )
    else:
        fl = tmp_path / "design.f"
        fl.write_text(
            "\n".join(str(p.resolve()) for p in (a_v, b_v, c_v, d_v)) + "\n",
            encoding="utf-8",
        )
    return fl


def test_path_walk_abcd_chain(tmp_path: Path):
    fl_path = _write_abcd_design(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    request = ConnectivityRequest(
        checks=(ConnectivityCheck("A.B.C.D", "A.B.C.D"),),
        top="A",
    )
    batch, index, state = run_path_walk_connect(
        request,
        fl,
        top="A",
        no_cache=True,
    )
    assert "A.B.C.D" in state.rows_by_path
    assert batch.results[0].connected is True
    assert index.get_module("D") is not None


def test_path_walk_abcd_with_library_stub(tmp_path: Path):
    fl_path = _write_abcd_design(tmp_path, with_lib_stub=True)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    request = ConnectivityRequest(
        checks=(ConnectivityCheck("A.B.C.D", "A.B.C.D"),),
        top="A",
    )
    batch, index, state = run_path_walk_connect(
        request,
        fl,
        top="A",
        no_cache=True,
    )
    assert "A.B.C.D" in state.rows_by_path
    assert batch.results[0].connected is True
    b_rec = index.get_module("B")
    c_rec = index.get_module("C")
    assert b_rec is not None and not b_rec.is_blackbox
    assert c_rec is not None and not c_rec.is_blackbox
    assert len(c_rec.instances) >= 1