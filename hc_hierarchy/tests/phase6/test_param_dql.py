"""Item 3: parameter overrides in index + DQL param ~."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_param_override_extracted():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    p = Path("/tmp/hch_param_extract.v")
    p.write_text(
        """
module child #(parameter W=8)(input clk);
endmodule
module top(input clk);
  child #(.W(16)) u_a (.clk(clk));
endmodule
""",
        encoding="utf-8",
    )
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    edge = mods["top"].instances[0]
    assert edge.param_overrides.get("W") == "16"


@pytest.mark.requires_engine
def test_param_dql_query(tmp_path):
    import sqlite3

    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import plan_dql

    p = tmp_path / "param.v"
    p.write_text(
        """
module child #(parameter W=8)(input clk);
endmodule
module top(input clk);
  child #(.W(32)) u_a (.clk(clk));
endmodule
""",
        encoding="utf-8",
    )
    fl = tmp_path / "mini.f"
    fl.write_text(f"{p}\n", encoding="utf-8")
    db = tmp_path / "p.hch.db"
    build_index_from_filelist(str(fl), str(db), top_module="top")
    plan = plan_dql('param ~ "W" AND module = "child"')
    con = sqlite3.connect(db)
    rows = con.execute(plan.sql, plan.params).fetchall()
    con.close()
    assert len(rows) >= 1