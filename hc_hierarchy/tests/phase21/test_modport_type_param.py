"""Phase 21: modport tag + type param child_type."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_modport_child_kind():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees


    code = """
    interface bus_if;
      modport master(input clk);
    endinterface
    module top;
      bus_if u_if();
      bus_if dut (u_if);
    endmodule
    """
    p = Path("/tmp/hch_modport.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    assert mods["bus_if"].module_kind == "interface"
    assert len(mods["top"].instances) >= 2