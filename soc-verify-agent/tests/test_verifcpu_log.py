"""Unit tests for VerifCPU log integrity scanning (_verifcpu.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

OPS_SANITY = Path(__file__).resolve().parents[1] / "projects" / "VERIF-CPU-SOC" / "ops" / "sanity"
sys.path.insert(0, str(OPS_SANITY))

from _verifcpu import (  # noqa: E402
    judge_log,
    scan_log_integrity,
)


def _block(cmd: str, exit_code: str | int, body: str = "") -> str:
    return (
        f"\n{'=' * 72}\n"
        f"$ {cmd}\n"
        f"(cwd=/tmp)\n"
        f"exit={exit_code}\n\n"
        f"{body}"
    )


def test_scan_detects_sigkill_exit():
    text = _block("vvp sim_build/tb.vvp", 137, "")
    hits = scan_log_integrity(text)
    assert any("exit=137" in h and "sigkill" in h for h in hits)


def test_scan_detects_timeout_exit():
    text = _block("vvp sim_build/tb.vvp", "TIMEOUT", "subprocess timeout after 7200s\n")
    hits = scan_log_integrity(text)
    assert any("TIMEOUT" in h for h in hits)


def test_scan_detects_incomplete_cmd_block():
    text = f"\n{'=' * 72}\n$ make sim_build/foo.vvp\n(cwd=/tmp)\npartial output\n"
    hits = scan_log_integrity(text)
    assert any("incomplete cmd block" in h for h in hits)


def test_scan_detects_vvp_missing_artifact():
    text = _block(
        "vvp sim_build/missing.vvp",
        0,
        "sim_build/missing.vvp: Unable to open input file.\n",
    )
    hits = scan_log_integrity(text)
    assert any("silent fail" in h or "Unable to open" in h for h in hits)


def test_scan_detects_vvp_abrupt_tail():
    text = _block("vvp sim_build/tb.vvp", 0, "VCD info: dumpfile opened\n")
    hits = scan_log_integrity(text)
    assert any("no completion in last" in h for h in hits)


def test_scan_passes_complete_vvp_tail():
    text = _block(
        "vvp sim_build/tb.vvp",
        0,
        "Checklist: 43 passed / 0 failed\n[SUCCESS] iverilog campaign passed\n",
    )
    assert scan_log_integrity(text) == []


def test_judge_log_fails_on_kill_without_error_keyword(tmp_path: Path):
    log = tmp_path / "rtl_sim.log"
    log.write_text(
        "# gate=rtl_sim\n"
        + _block("vvp sim_build/tb_full_campaign.vvp", 137, ""),
        encoding="utf-8",
    )
    result = judge_log(log, gate="rtl_sim")
    assert not result.ok
    assert any("exit=137" in h for h in result.hits)