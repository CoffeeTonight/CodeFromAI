"""pyslang extract: generate if/for nesting."""

import pytest


@pytest.mark.requires_engine
def test_generate_if_for_instances_extracted():
    from pathlib import Path

    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top(input clk, rst_n);
      genvar gi;
      generate
        if (1) begin : g_if
          for (gi = 0; gi < 2; gi++) begin : g_loop
            uart16550 u_uart (.clk(clk), .rst_n(rst_n));
          end
        end else begin : g_else
          spi_master u_spi (.clk(clk), .rst_n(rst_n));
        end
      endgenerate
    endmodule
    """
    p = Path("/tmp/hch_gen_extract.v")
    p.write_text(code)
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    names = {e.inst_name for e in mods["top"].instances}
    assert "u_uart" in names
    assert "u_spi" not in names