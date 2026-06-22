"""Conditional multi-review consensus for validation_judge (uncertainty-gated)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml


def load_consensus_spec(root: Path) -> dict[str, Any]:
    spec_path = root / "registry" / "validation_autonomy_spec.yaml"
    if not spec_path.is_file():
        spec_path = Path(__file__).resolve().parents[2] / "registry" / "validation_autonomy_spec.yaml"
    return load_yaml(spec_path) or {}


def compute_item_uncertainty(items_payload: dict[str, Any]) -> float:
    items = items_payload.get("items") or []
    if not items:
        return 0.0
    failing = [i for i in items if i.get("status") == "fail"]
    if not failing:
        return 0.0
    total = len(items)
    ratio = len(failing) / max(total, 1)
    borderline = 0.35 if len(failing) == 1 and total > 2 else 0.0
    return round(max(ratio * 0.5, borderline), 4)


def needs_consensus(
    judgment: dict[str, Any],
    items_payload: dict[str, Any],
    *,
    threshold: float = 0.3,
) -> bool:
    if judgment.get("source") == "consensus":
        return False
    seq = str(judgment.get("sequence_action") or "")
    if seq in ("continue_remaining", "partial_accept"):
        return True
    return compute_item_uncertainty(items_payload) >= threshold


def _vote_sequence_action(votes: list[str]) -> str:
    if not votes:
        return "halt"
    counts: dict[str, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=lambda k: (counts[k], k))


def apply_consensus(
    judgment: dict[str, Any],
    items_payload: dict[str, Any],
    run_dir: Path,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    root = root or Path.cwd()
    spec = load_consensus_spec(root)
    consensus_cfg = spec.get("consensus") or {}
    threshold = float(consensus_cfg.get("uncertainty_threshold", 0.3))

    if not needs_consensus(judgment, items_payload, threshold=threshold):
        judgment["uncertainty"] = compute_item_uncertainty(items_payload)
        return judgment

    primary = str(judgment.get("sequence_action") or "retry_gate")
    uncertainty = compute_item_uncertainty(items_payload)

    # Mechanical reviewer votes — conservative bias on risky actions
    votes = [primary]
    if primary in ("continue_remaining", "partial_accept"):
        votes.append("retry_gate")
        votes.append("retry_gate")
    elif uncertainty >= 0.5:
        votes.append("retry_gate")
    else:
        votes.append(primary)

    final_action = _vote_sequence_action(votes)
    out = dict(judgment)
    out["source"] = "consensus"
    out["uncertainty"] = uncertainty
    out["consensus"] = {
        "votes": votes,
        "sequence_action": final_action,
        "required_for": (
            "risky_sequence_action"
            if primary in ("continue_remaining", "partial_accept")
            else "high_uncertainty"
        ),
    }
    out["sequence_action"] = final_action

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "validation_consensus.json").write_text(
        json.dumps(out.get("consensus") or {}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "validation_judgment.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out