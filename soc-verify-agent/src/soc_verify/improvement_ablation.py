"""Link meta proposals to next-run deltas — causal improvement tracking."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.improvement_eval import load_history
from soc_verify.models import load_yaml, save_yaml


ABLATION_NAME = "improvement_ablation.json"
PROJECT_ABLATION = "improvement/ablation_history.yaml"


def _last_queued_proposal(project_dir: Path, before_run_id: str) -> dict[str, Any] | None:
    queue_dir = project_dir / "meta_proposals"
    if not queue_dir.is_dir():
        return None
    candidates: list[tuple[str, dict[str, Any]]] = []
    for p in queue_dir.glob("*.json"):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rid = str(rec.get("run_id", p.stem))
        if rid == before_run_id:
            continue
        if rec.get("status") == "queued":
            candidates.append((rid, rec))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


def build_ablation_record(
    project_dir: Path,
    run_dir: Path,
    *,
    run_id: str,
    stage: str,
    group: str,
    snapshot: dict[str, Any],
    branch_scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    history = load_history(project_dir, stage, group)
    prev = history[-2] if len(history) >= 2 else (history[-1] if history else None)
    proposal_rec = _last_queued_proposal(project_dir, run_id)

    delta_vs_prev: dict[str, float] = {}
    if prev:
        cur_idx = float(snapshot.get("improvement_index", 0))
        prev_idx = float(prev.get("improvement_index", 0))
        delta_vs_prev["improvement_index"] = round(cur_idx - prev_idx, 4)
        for key in ("completeness", "trust_score", "verdict_pass", "parity_ok"):
            cur_v = (snapshot.get("delta_vs_previous") or {}).get(key)
            if cur_v is not None:
                delta_vs_prev[key] = float(cur_v)

    proposal_summary = None
    if proposal_rec:
        prop = proposal_rec.get("proposal") or {}
        proposal_summary = {
            "proposal_run_id": prop.get("run_id"),
            "summary": prop.get("summary"),
            "changes": [
                {
                    "layer": c.get("layer"),
                    "target": c.get("target"),
                    "rationale": c.get("rationale"),
                }
                for c in (prop.get("changes") or [])
                if isinstance(c, dict)
            ],
            "queued_at": proposal_rec.get("queued_at"),
        }

    return {
        "contract": "improvement_ablation_v1",
        "run_id": run_id,
        "as_of": date.today().isoformat(),
        "stage": stage,
        "group": group,
        "linked_proposal": proposal_summary,
        "snapshot_improvement_index": snapshot.get("improvement_index"),
        "delta_vs_previous_run": delta_vs_prev,
        "branch_success_mean": _branch_success_mean(branch_scorecard),
        "hypothesis": (
            "proposal applied between runs" if proposal_summary else "no prior queued proposal"
        ),
    }


def _branch_success_mean(scorecard: dict[str, Any] | None) -> float | None:
    if not scorecard:
        return None
    branches = scorecard.get("branches") or []
    if not branches:
        return None
    vals = [float(b.get("success_rate", 0)) for b in branches]
    return round(sum(vals) / len(vals), 4)


def write_ablation(run_dir: Path, record: dict[str, Any]) -> Path:
    path = run_dir / ABLATION_NAME
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def append_ablation_history(project_dir: Path, record: dict[str, Any]) -> None:
    path = project_dir / PROJECT_ABLATION
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path)
    if not data:
        data = {"contract": "ablation_history_v1", "entries": []}
    entries = list(data.get("entries") or [])
    entries.append(record)
    if len(entries) > 300:
        entries = entries[-300:]
    data["entries"] = entries
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)