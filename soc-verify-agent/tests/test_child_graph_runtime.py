from __future__ import annotations

import json
from pathlib import Path

from soc_verify.child_graph_runtime import child_key_for_node, validate_child_after_complete


ROOT = Path(__file__).resolve().parents[1]


def test_child_key_mapping():
    assert child_key_for_node("promote") == "promote"
    assert child_key_for_node("parity_check") == "runner_loop"


def test_child_runtime_blocks_incomplete_promote(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(ROOT / "projects" / "EXAMPLE-SOC"),
        "project_id": "EXAMPLE-SOC",
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "PASS",
        "parity_ok": True,
    }
    result = validate_child_after_complete(
        ROOT, "verify_group", "promote", state=state, run_dir=run_dir
    )
    assert result.ok is False
    assert result.failed_steps