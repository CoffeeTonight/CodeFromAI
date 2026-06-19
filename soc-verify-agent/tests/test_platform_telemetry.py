from __future__ import annotations

import json
from pathlib import Path

from soc_verify.platform_telemetry import (
    code_change_summary,
    ensure_platform_baseline,
    record_code_change,
    record_platform_use,
)


def test_baseline_first_start_then_increment(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    b1 = ensure_platform_baseline(root, trigger="test")
    assert b1.get("first_started_at")
    assert b1.get("use_count") == 1

    b2 = ensure_platform_baseline(root, trigger="test2")
    assert b2.get("use_count") == 2
    assert b1["first_started_at"] == b2["first_started_at"]


def test_record_use_and_code_change(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    ensure_platform_baseline(root, trigger="init")
    record_platform_use(
        root,
        kind="verify",
        graph_id="verify_group",
        run_id="r1",
        verdict="PASS",
        trust_score=0.8,
        success_rate=1.0,
    )
    record_platform_use(
        root,
        kind="verify",
        graph_id="verify_group",
        run_id="r2",
        verdict="FAIL",
        trust_score=0.7,
        success_rate=0.0,
    )
    record_code_change(
        root,
        run_id="r1",
        project_id="P",
        layer="ops",
        target="ops/sim/g.py",
        rationale="parity fix",
        source="crystallize",
        applied=True,
    )
    summary = code_change_summary(root)
    assert summary["total"] == 1
    assert summary["by_layer"]["ops"] == 1