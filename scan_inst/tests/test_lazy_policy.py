"""Lazy policy: defer ifdef/macro at index by default."""

from __future__ import annotations

from pathlib import Path

from scan_inst.lazy_scope import lazy_index_ifdef, lazy_processing_enabled
from scan_inst.preprocess import clear_include_unit_cache, preprocess_file_for_index


def test_lazy_default_on(monkeypatch):
    monkeypatch.delenv("SCAN_INST_LAZY", raising=False)
    assert lazy_processing_enabled() is True
    assert lazy_index_ifdef() is False


def test_lazy_index_defers_ifdef_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SCAN_INST_LAZY", raising=False)
    monkeypatch.delenv("SCAN_INST_LAZY_IFDEF", raising=False)
    rtl = tmp_path / "top.v"
    rtl.write_text(
        "`define ON 1\n"
        "`ifdef ON\n"
        "module top; leaf_a u_a (); endmodule\n"
        "`else\n"
        "module top; leaf_b u_b (); endmodule\n"
        "`endif\n",
        encoding="utf-8",
    )
    clear_include_unit_cache()
    text = preprocess_file_for_index(rtl, [tmp_path], {"ON": "1"})
    assert "leaf_a" in text
    assert "leaf_b" in text


def test_lazy_index_ifdef_opt_in(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SCAN_INST_LAZY", "1")
    monkeypatch.setenv("SCAN_INST_LAZY_IFDEF", "1")
    rtl = tmp_path / "top.v"
    rtl.write_text(
        "`define ON 1\n"
        "`ifdef ON\n"
        "module top; leaf_a u_a (); endmodule\n"
        "`else\n"
        "module top; leaf_b u_b (); endmodule\n"
        "`endif\n",
        encoding="utf-8",
    )
    clear_include_unit_cache()
    text = preprocess_file_for_index(rtl, [tmp_path], {"ON": "1"})
    assert "leaf_a" in text
    assert "leaf_b" not in text