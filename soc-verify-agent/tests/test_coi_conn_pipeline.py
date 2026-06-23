"""COI hierarchy → conn producer-consumer pipeline helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COI_OPS = ROOT / "projects" / "VERIF-CPU-SOC" / "ops" / "static"
sys_path_insert = str(COI_OPS)
import sys

if sys_path_insert not in sys.path:
    sys.path.insert(0, sys_path_insert)

from _coi_conn import (  # noqa: E402
    VALIDATED_ARTIFACT,
    build_hierwalk_connect_cmd,
    endpoint_specs_from_checks,
    path_walk_connect_artifact_paths,
    read_validated_artifact,
    hierwalk_batch_payload,
    wait_for_validated_checks,
    write_validated_artifact,
)


def test_endpoint_specs_dedupes_a_b():
    checks = [
        {"id": "x", "a": "top.u_a.sig", "b": "top.u_b.sig", "expected_connected": True},
        {"id": "y", "a": "top.u_a.sig", "b": "top.u_c.sig", "expected_connected": False},
    ]
    specs = endpoint_specs_from_checks(checks)
    assert specs == ["top.u_a.sig", "top.u_b.sig", "top.u_c.sig"]


def test_hierwalk_batch_payload_subset():
    spec = {
        "top": "chip_top",
        "connect_trace": True,
        "checks": [
            {"id": "a", "a": "top.u1", "b": "top.u2", "expected_connected": True},
            {"id": "b", "a": "top.u3", "b": "top.u4", "expected_connected": False},
        ],
    }
    subset = [spec["checks"][0]]
    payload = hierwalk_batch_payload(spec, checks=subset)
    assert payload["top"] == "chip_top"
    assert payload["connect_log"] is True
    assert len(payload["checks"]) == 1
    assert payload["checks"][0]["id"] == "a"


def test_wait_blocks_until_validated(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log_path = run_dir / "coi_conn.log"

    def _producer() -> None:
        time.sleep(0.3)
        write_validated_artifact(
            run_dir,
            {
                "status": "running",
                "validated_checks": [],
                "failed_checks": [],
            },
        )
        time.sleep(0.3)
        write_validated_artifact(
            run_dir,
            {
                "status": "complete",
                "validated_checks": [{"id": "ok", "a": "t.a", "b": "t.b", "expected_connected": True}],
                "failed_checks": [],
            },
        )

    import threading

    threading.Thread(target=_producer, daemon=True).start()
    t0 = time.monotonic()
    body = wait_for_validated_checks(
        run_dir,
        log_path=log_path,
        timeout_sec=5.0,
        poll_sec=0.05,
    )
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.25
    assert len(body.get("validated_checks") or []) == 1
    assert read_validated_artifact(run_dir / VALIDATED_ARTIFACT) is not None


def test_build_hierwalk_connect_cmd_uses_path_walk_mode(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    fl = rtl / "fl.f"
    batch = rtl / "batch.json"
    out = rtl / "coi_conn.tsv"
    cmd = build_hierwalk_connect_cmd(
        scan_bin="/usr/bin/hier-walk",
        filelist=fl,
        batch_json=batch,
        tsv_out=out,
        rtl_root=rtl,
        top="chip_top_example",
    )
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "path-walk"
    assert "--no-cache" in cmd
    assert "--check-connect-batch" in cmd


def test_path_walk_connect_artifact_paths_under_db_top(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    text_path, logical_path = path_walk_connect_artifact_paths(rtl, "chip_top_example")
    assert text_path == rtl / ".db_chip_top_example" / "conn.text.tsv"
    assert logical_path == rtl / ".db_chip_top_example" / "conn.tsv"


def test_wait_returns_complete_with_zero_validated(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_validated_artifact(
        run_dir,
        {
            "status": "complete",
            "validated_checks": [],
            "failed_checks": [{"id": "bad", "hierarchy_errors": ["a: miss"]}],
        },
    )
    body = wait_for_validated_checks(
        run_dir,
        log_path=run_dir / "coi_conn.log",
        timeout_sec=2.0,
        poll_sec=0.05,
    )
    assert body["status"] == "complete"
    assert body["validated_checks"] == []