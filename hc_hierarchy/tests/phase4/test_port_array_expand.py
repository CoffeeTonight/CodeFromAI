"""Packed/unpacked port array expansion and DQL port_path queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hch.ingest.port_array_expand import expand_port_name, materialized_port_names
from hch.schema import PortRecord


def test_expand_packed_range_descending():
    assert expand_port_name("int", "[2:0]") == [
        "int[2]",
        "int[1]",
        "int[0]",
        "int[2:0]",
    ]


def test_expand_packed_range_ascending():
    assert expand_port_name("sel", "[5:1]") == [
        "sel[5]",
        "sel[4]",
        "sel[3]",
        "sel[2]",
        "sel[1]",
        "sel[5:1]",
    ]


def test_expand_single_index_means_down_to_zero():
    assert expand_port_name("idx", "[3]") == [
        "idx[3]",
        "idx[2]",
        "idx[1]",
        "idx[0]",
        "idx[3:0]",
    ]


def test_scalar_port_unchanged():
    assert expand_port_name("clk", "") == ["clk"]


def test_expand_2d_partial_range_alias():
    names = expand_port_name("data", "[1:0][9:8]")
    assert "data[1][9]" in names
    assert "data[1][9:8]" in names
    assert "data[0][9:8]" in names
    assert "data[1:0][9:8]" in names


@pytest.mark.requires_engine
def test_index_and_query_port_path_indices(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import apply_post_filters, plan_dql

    rtl = tmp_path / "arr_ports.v"
    fl = tmp_path / "arr.f"
    rtl.write_text(
        """
module leaf(
    input  logic        clk,
    input  logic [2:0]  data,
    input  logic [5:1]  sel,
    input  logic [3]    idx
);
endmodule
module top;
    leaf u_leaf();
endmodule
""",
        encoding="utf-8",
    )
    fl.write_text(f"{rtl.resolve()}\n-top top\n", encoding="utf-8")
    db = tmp_path / "arr.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="top")
    store.close()

    conn = sqlite3.connect(db)
    port_names = {
        r[0]
        for r in conn.execute(
            """
            SELECT ip.port_name FROM instance_ports ip
            JOIN instances i ON i.id = ip.instance_id
            WHERE i.full_path = 'top.u_leaf'
            """
        )
    }
    conn.close()
    assert "data[2]" in port_names
    assert "data[2:0]" in port_names
    assert "sel[5:1]" in port_names
    assert "idx[3]" in port_names
    assert "clk" in port_names

    def rows(q: str):
        plan = plan_dql(q)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        out = apply_post_filters(
            [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()],
            plan,
        )
        conn.close()
        return out

    hit = rows('expand_ports AND port_path = "top.u_leaf.idx[3]"')
    assert len(hit) == 1
    assert hit[0]["port_name"] == "idx[3]"

    hit_range = rows('expand_ports AND port_path = "top.u_leaf.sel[5:1]"')
    assert len(hit_range) == 1
    assert hit_range[0]["port_name"] == "sel[5:1]"

    hit_prefix = rows('expand_ports AND port_path ^= "top.u_leaf.idx"')
    paths = {r["port_path"] for r in hit_prefix}
    assert "top.u_leaf.idx[2]" in paths
    assert "top.u_leaf.idx[3:0]" in paths


@pytest.mark.requires_engine
def test_extract_width_from_pyslang_ports():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    p = Path("/tmp/hch_arr_ports_extract.v")
    p.write_text(
        "module leaf(input logic [2:0] data, input logic [5:1] sel); endmodule\n",
        encoding="utf-8",
    )
    mods = {
        m.module_name: m
        for m in extract_modules_from_trees(parse_syntax_trees([p]), str(p))
    }
    by_name = {pr.name: pr.width for pr in mods["leaf"].ports}
    assert by_name["data"] == "[2:0]"
    assert by_name["sel"] == "[5:1]"
    names = materialized_port_names(mods["leaf"].ports)
    assert "data[1]" in names
    assert "sel[5:1]" in names


@pytest.mark.requires_engine
def test_extract_keyword_port_name_int():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    p = Path("/tmp/hch_int_port_extract.v")
    p.write_text(
        "module leaf(input logic [1:0][9:8] int); endmodule\n",
        encoding="utf-8",
    )
    mods = {
        m.module_name: m
        for m in extract_modules_from_trees(parse_syntax_trees([p]), str(p))
    }
    by_name = {pr.name: pr.width for pr in mods["leaf"].ports}
    assert by_name["int"] == "[1:0][9:8]"
    names = materialized_port_names(mods["leaf"].ports)
    assert "int[1][9:8]" in names
    assert "int[1][9]" in names


@pytest.mark.requires_engine
def test_index_and_query_2d_port_path(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import apply_post_filters, plan_dql

    rtl = tmp_path / "arr2d.v"
    fl = tmp_path / "arr2d.f"
    rtl.write_text(
        """
module mid(input logic [1:0][9:8] int);
endmodule
module top;
    mid u();
endmodule
""",
        encoding="utf-8",
    )
    fl.write_text(f"{rtl.resolve()}\n-top top\n", encoding="utf-8")
    db = tmp_path / "arr2d.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="top")
    store.close()

    def rows(q: str):
        plan = plan_dql(q)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        out = apply_post_filters(
            [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()],
            plan,
        )
        conn.close()
        return out

    hit = rows('expand_ports AND port_path = "top.u.int[1][9]"')
    assert len(hit) == 1
    assert hit[0]["port_name"] == "int[1][9]"

    hit_alias = rows('expand_ports AND port_path = "top.u.int[1][9:8]"')
    assert len(hit_alias) == 1
    assert hit_alias[0]["port_name"] == "int[1][9:8]"