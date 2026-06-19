"""Experiment tagging — campaign / condition / hypothesis for paper factory."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml


EXPERIMENT_RUN_NAME = "experiment_run.json"
CAMPAIGNS_REGISTRY = "paper_campaigns.yaml"
EVAL_MANIFEST = "evaluation_manifest.yaml"
EXPERIMENT_SPEC = "experiment_spec.yaml"


def _registry(root: Path) -> Path:
    return root / "registry"


def load_evaluation_manifest(root: Path) -> dict[str, Any]:
    return load_yaml(_registry(root) / EVAL_MANIFEST)


def load_experiment_spec(root: Path) -> dict[str, Any]:
    return load_yaml(_registry(root) / EXPERIMENT_SPEC)


def resolve_experiment_tags(
    root: Path,
    *,
    campaign: str = "",
    condition: str = "",
    hypothesis: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Resolve tags from CLI, env, or config.json paper block."""
    spec = load_experiment_spec(root)
    eval_m = load_evaluation_manifest(root)

    camp = (
        campaign
        or os.environ.get("SOC_VERIFY_CAMPAIGN", "")
        or _paper_config(root).get("default_campaign", "")
        or str(eval_m.get("campaign_default", "dev"))
    )
    cond = condition or os.environ.get("SOC_VERIFY_CONDITION", "") or "treatment_full"
    hyp = hypothesis or os.environ.get("SOC_VERIFY_HYPOTHESIS", "") or ""

    return {
        "contract": "experiment_run_v1",
        "campaign": camp,
        "condition": cond,
        "hypothesis": hyp,
        "notes": notes,
        "tagged_at": datetime.now(timezone.utc).isoformat(),
        "condition_spec": (spec.get("conditions") or {}).get(cond, {}),
    }


def _paper_config(root: Path) -> dict[str, Any]:
    try:
        from soc_verify.config import load_user_config

        return (load_user_config(root).raw.get("paper") or {})
    except FileNotFoundError:
        return {}


def write_experiment_run(run_dir: Path, tags: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / EXPERIMENT_RUN_NAME
    path.write_text(json.dumps(tags, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_experiment_run(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / EXPERIMENT_RUN_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def register_campaign_run(root: Path, tags: dict[str, Any], *, run_meta: dict[str, Any]) -> None:
    path = _registry(root) / CAMPAIGNS_REGISTRY
    data = load_yaml(path)
    if not data:
        data = {"contract": "paper_campaigns_v1", "campaigns": {}}
    camp = str(tags.get("campaign", "dev"))
    campaigns = data.setdefault("campaigns", {})
    bucket = campaigns.setdefault(camp, {"runs": []})
    runs = list(bucket.get("runs") or [])
    entry = {
        "registered_at": date.today().isoformat(),
        "campaign": camp,
        "condition": tags.get("condition"),
        "hypothesis": tags.get("hypothesis"),
        **run_meta,
    }
    runs.append(entry)
    if len(runs) > 1000:
        runs = runs[-1000:]
    bucket["runs"] = runs
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)


def find_runs_for_campaign(root: Path, campaign: str) -> list[dict[str, Any]]:
    """Discover runs tagged with campaign across all projects."""
    found: list[dict[str, Any]] = []
    projects = root / "projects"
    if not projects.is_dir():
        return found

    for project_dir in projects.iterdir():
        if not project_dir.is_dir():
            continue
        runs_dir = project_dir / "runs"
        if not runs_dir.is_dir():
            continue
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            exp = load_experiment_run(run_dir)
            if not exp or str(exp.get("campaign")) != campaign:
                continue
            found.append(
                {
                    "project_id": project_dir.name,
                    "run_id": run_dir.name,
                    "run_dir": str(run_dir),
                    "experiment": exp,
                }
            )
    return found


def evaluation_progress(root: Path, campaign: str) -> dict[str, Any]:
    """How many evaluation_manifest gates have PASS in this campaign."""
    manifest = load_evaluation_manifest(root)
    gates = list(manifest.get("gates") or [])
    runs = find_runs_for_campaign(root, campaign)
    criteria = manifest.get("success_criteria") or {}

    results: list[dict[str, Any]] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        pid = str(gate.get("project_id", ""))
        stage = str(gate.get("stage", ""))
        group = str(gate.get("group", ""))
        match = None
        for r in runs:
            if r["project_id"] != pid:
                continue
            snap_path = Path(r["run_dir"]) / "improvement_snapshot.json"
            if not snap_path.is_file():
                continue
            try:
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if snap.get("stage") == stage and snap.get("group") == group:
                match = snap
                break
        verdict = match.get("verdict") if match else None
        idx = float(match.get("improvement_index", 0)) if match else 0.0
        trust = float(match.get("trust_score", 0)) if match else 0.0
        ok = (
            verdict == criteria.get("verdict", "PASS")
            and idx >= float(criteria.get("min_improvement_index", 0))
            and trust >= float(criteria.get("min_trust_score", 0))
        )
        project_path = root / "projects" / pid
        results.append(
            {
                **gate,
                "evaluated": match is not None,
                "verdict": verdict,
                "improvement_index": idx if match else None,
                "trust_score": trust if match else None,
                "criteria_ok": ok if match else False,
                "project_present": project_path.is_dir(),
            }
        )

    done = sum(1 for r in results if r.get("criteria_ok"))
    return {
        "contract": "evaluation_progress_v1",
        "campaign": campaign,
        "gates_total": len(results),
        "gates_passing": done,
        "gates": results,
    }