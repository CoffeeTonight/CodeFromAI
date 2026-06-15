"""Large module fast path: skip body parameter scan, keep instance discovery."""

from __future__ import annotations

import time

from scan_inst.index import scan_preprocessed
from scan_inst.params import (
    body_param_scan_skipped,
    collect_body_params_closure,
    collect_index_module_params,
    collect_module_params,
    strip_body_param_declarations,
)
from scan_inst.perf import body_param_scan_max


def _huge_param_block(count: int) -> str:
    return "\n".join(f"parameter P{i} = {i};" for i in range(count))


def test_body_param_scan_skipped_threshold():
    assert body_param_scan_max() == 512 * 1024
    body = "x" * (512 * 1024 + 1)
    assert body_param_scan_skipped(body) is True
    assert body_param_scan_skipped("small") is False


def test_collect_module_params_skips_large_body(monkeypatch):
    monkeypatch.setenv("SCAN_INST_BODY_PARAM_SCAN_MAX", "100")
    header = "parameter H = 1"
    body = _huge_param_block(50) + "\nparameter BODY_ONLY = 99;"
    params = collect_module_params(header, body)
    assert params == {"H": "1"}
    assert "BODY_ONLY" not in params


def test_collect_module_params_small_body_still_scans(monkeypatch):
    monkeypatch.setenv("SCAN_INST_BODY_PARAM_SCAN_MAX", "10000")
    header = ""
    body = "parameter A = 1;\nlocalparam B = 2;"
    params = collect_module_params(header, body)
    assert params == {"A": "1", "B": "2"}


def test_strip_body_param_declarations_keeps_instances():
    body = "parameter X = 1;\nchild u1 ();\nparameter Y = 2;\nother u2 ();"
    stripped = strip_body_param_declarations(body)
    assert "parameter" not in stripped
    assert "child u1" in stripped
    assert "other u2" in stripped


def test_scan_preprocessed_huge_params_few_instances(monkeypatch):
    monkeypatch.setenv("SCAN_INST_BODY_PARAM_SCAN_MAX", "200")
    params = _huge_param_block(5000)
    text = f"""module top #(
  parameter WIDTH = 8
) (
  input clk
);
{params}
leaf_a u_a ();
leaf_b u_b (.clk(clk));
endmodule
"""
    t0 = time.perf_counter()
    mods = scan_preprocessed(text, "big.v")
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"scan took {elapsed:.1f}s"
    rec = mods["top"]
    children = {e.child_module for e in rec.instances}
    assert children == {"leaf_a", "leaf_b"}
    assert "WIDTH" in rec.raw_params
    assert "P0" not in rec.raw_params


def test_collect_body_params_closure_finds_chain():
    body = "\n".join(
        [
            "parameter P0 = 0;",
            "parameter WIDTH = DEPTH;",
            "parameter DEPTH = 16;",
        ]
    )
    got = collect_body_params_closure(body, {"WIDTH"})
    assert got == {"WIDTH": "DEPTH", "DEPTH": "16"}


def test_scan_preprocessed_resolves_dim_param_from_body(monkeypatch):
    monkeypatch.setenv("SCAN_INST_BODY_PARAM_SCAN_MAX", "200")
    noise = _huge_param_block(3000)
    text = f"""module top;
{noise}
parameter WIDTH = 4;
leaf u [WIDTH-1:0] ();
endmodule
"""
    mods = scan_preprocessed(text, "dim.v")
    rec = mods["top"]
    assert "WIDTH" in rec.raw_params
    assert rec.raw_params["WIDTH"] == "4"
    assert "P0" not in rec.raw_params
    names = {e.inst_name for e in rec.instances}
    assert names == {"u[0]", "u[1]", "u[2]", "u[3]"}


def test_collect_index_module_params_instance_first(monkeypatch):
    monkeypatch.setenv("SCAN_INST_BODY_PARAM_SCAN_MAX", "50")
    body = _huge_param_block(100) + "\nparameter NEED = 3;"
    params = collect_index_module_params("", body, ["NEED-1:0"])
    assert params == {"NEED": "3"}
    assert "P0" not in params