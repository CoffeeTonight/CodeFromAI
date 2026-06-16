"""Config env audit logging."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scan_inst.config_env_audit import (
    format_config_env_audit_lines,
    format_verilog_defines_audit_lines,
)
from scan_inst.preprocess import _define_active
from scan_inst.run_request import apply_config_env_from_document


def test_format_config_env_audit_shows_json_env_and_policy(monkeypatch):
    monkeypatch.delenv("SCAN_INST_LAZY", raising=False)
    monkeypatch.delenv("SCAN_INST_LAZY_IFDEF", raising=False)
    doc = {
        "defines": {"ABC": "1"},
        "env": {"SCAN_INST_LAZY_IFDEF": "1"},
    }
    applied = apply_config_env_from_document(doc)
    lines = format_config_env_audit_lines(doc, json_env_applied=applied)
    text = "\n".join(lines)
    assert "JSON env block declared" in text
    assert "SCAN_INST_LAZY_IFDEF=1" in text
    assert "source=json:env" in text
    assert "verilog-defines from JSON top-level: ABC=1" in text
    assert "active-at-index" in text
    assert "index-ifdef-policy" in text


def test_define_active_for_ifndef_semantics():
    assert _define_active("ABC", {}) is False
    assert _define_active("ABC", {"ABC": "0"}) is False
    assert _define_active("ABC", {"ABC": ""}) is False
    assert _define_active("ABC", {"ABC": "false"}) is False
    assert _define_active("ABC", {"ABC": "1"}) is True


def test_verilog_defines_audit_merged_and_ifndef_hints():
    lines = format_verilog_defines_audit_lines(
        effective_defines={"ABC": "0", "SYNTH": "1"},
        json_defines={"ABC": "0"},
        connect_defines={},
    )
    text = "\n".join(lines)
    assert "from JSON defines" in text
    assert "ABC='0'" in text
    assert "SYNTH='1'" in text
    assert "`ifndef ABC`=ON" in text
    assert "`ifdef SYNTH`=ON" in text
    assert "`ifndef SYNTH`=OFF" in text
    assert "ifdef/ifndef semantics" in text


def test_cli_emits_verilog_defines_after_filelist(tmp_path: Path):
    (tmp_path / "top.v").write_text(
        """
module top;
`ifndef ABC
 DEF u_DEF (.QW());
`endif
endmodule
module DEF(output QW); endmodule
""",
        encoding="utf-8",
    )
    (tmp_path / "design.f").write_text("+define+SYNTH=1\ntop.v\n", encoding="utf-8")
    run_json = tmp_path / "run.json"
    run_json.write_text(
        json.dumps(
            {
                "filelist": "design.f",
                "top": "top",
                "defines": {"ABC": "0"},
                "no_cache": True,
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["scan-inst", str(run_json)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert "verilog-defines:" in proc.stderr
    assert "`ifndef ABC`=ON" in proc.stderr
    assert "`ifndef SYNTH`=OFF" in proc.stderr
    assert "top.u_DEF" in proc.stdout


def test_cli_emits_config_env_audit(tmp_path: Path):
    run_json = tmp_path / "run.json"
    run_json.write_text(
        json.dumps(
            {
                "filelist": "missing.f",
                "env": {"SCAN_INST_LAZY_IFDEF": "1"},
                "defines": {},
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["scan-inst", str(run_json)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert "config-env:" in proc.stderr
    assert "SCAN_INST_LAZY_IFDEF=1" in proc.stderr
    assert "index-ifdef-policy" in proc.stderr