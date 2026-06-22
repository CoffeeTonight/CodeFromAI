from __future__ import annotations

from pathlib import Path

from soc_verify.validation_consensus import apply_consensus, compute_item_uncertainty, needs_consensus

ROOT = Path(__file__).resolve().parents[1]


def test_high_uncertainty_triggers_consensus(tmp_path: Path):
    items = {
        "items": [
            {"item_id": "t1", "status": "pass"},
            {"item_id": "t2", "status": "fail"},
            {"item_id": "t3", "status": "pass"},
        ],
        "failing_count": 1,
    }
    assert compute_item_uncertainty(items) >= 0.3

    judgment = {
        "contract": "validation_judgment_v1",
        "source": "llm",
        "sequence_action": "partial_accept",
        "items": [],
    }
    assert needs_consensus(judgment, items) is True

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    out = apply_consensus(judgment, items, run_dir, root=ROOT)
    assert out["source"] == "consensus"
    assert out["sequence_action"] == "retry_gate"
    assert (run_dir / "validation_judgment.json").is_file()