"""Config env audit logging."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scan_inst.config_env_audit import format_config_env_audit_lines
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