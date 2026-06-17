"""Path-walk: resolving ``c`` in ``a.b.c.d`` (split decls, arrays, generate-fold)."""

from __future__ import annotations

from pathlib import Path

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import run_path_walk_connect


def _run(tmp_path: Path, files: dict[str, str], path: str, *, top: str = "A") -> bool:
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    fl = tmp_path / "design.f"
    fl.write_text(
        "\n".join(str((tmp_path / name).resolve()) for name in files) + "\n",
        encoding="utf-8",
    )
    flr = parse_filelist(str(fl), index_cwd=str(tmp_path))
    request = ConnectivityRequest(
        checks=(ConnectivityCheck(path, path),),
        top=top,
    )
    _batch, _index, state = run_path_walk_connect(
        request,
        flr,
        top=top,
        no_cache=True,
    )
    return path in state.rows_by_path


def test_path_walk_c_only_in_second_b_decl(tmp_path: Path):
    """Other instances in first ``B`` decl; ``c`` only in a later duplicate module."""
    files = {
        "a.v": "module A; B B (); endmodule\n",
        "b1.v": "module B; X x (); Y y (); endmodule\n",
        "b2.v": "module B; X x (); Y y (); C c (); endmodule\n",
        "c.v": "module C; D d (); endmodule\n",
        "d.v": "module D; endmodule\n",
        "x.v": "module X; endmodule\n",
        "y.v": "module Y; endmodule\n",
    }
    assert _run(tmp_path, files, "A.B.c.d")


def test_path_walk_bare_c_requires_array_index(tmp_path: Path):
    """``c[0:1][0:1]`` must be addressed as ``c[i][j]``, not bare ``c``."""
    files = {
        "a.v": "module A; B b (); endmodule\n",
        "b.v": (
            "module B;\n"
            "  md2d_c c[0:1][0:1] ();\n"
            "endmodule\n"
        ),
        "md2d_c.v": "module md2d_c; D d (); endmodule\n",
        "d.v": "module D; endmodule\n",
    }
    assert not _run(tmp_path, files, "A.b.c.d", top="A")
    assert _run(tmp_path, files, "A.b.c[0][1].d", top="A")


def test_path_walk_generate_fold_child_before_index_apply(tmp_path: Path):
    """Tier-1 edge resolve must fold generate before matching folded inst names."""
    files = {
        "top.v": "module top; mid mid (); endmodule\n",
        "mid.v": (
            "module mid (input logic clk);\n"
            "  genvar gi;\n"
            "  generate\n"
            "    for (gi = 0; gi < 2; gi++) begin : gen_loop\n"
            "      leaf u ( .clk(clk) );\n"
            "    end\n"
            "  endgenerate\n"
            "endmodule\n"
        ),
        "leaf.v": "module leaf (input logic clk); endmodule\n",
    }
    path = "top.mid.gen_loop[0].u"
    assert _run(tmp_path, files, path, top="top")