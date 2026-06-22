"""Run spec freeze and drift measurement against verification MD/tag."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

FROZEN_NAME = "run_spec_frozen.yaml"
DRIFT_NAME = "drift_report.json"


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_run_spec(
    project_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    group: str,
    as_of: str,
) -> dict[str, Any]:
    group_dir = project_dir / "verification" / stage / group
    cache = load_yaml(project_dir / "cache.yaml")
    state = load_yaml(project_dir / "state.yaml")
    tag = str((cache.get("tag") or {}).get("value") or "")

    frozen: dict[str, Any] = {
        "contract": "run_spec_frozen_v1",
        "tag": tag,
        "stage": stage,
        "group": group,
        "check_sha256": _sha256_file(group_dir / "CHECK.md"),
        "manifest_sha256": _sha256_file(group_dir / "manifest.yaml"),
        "milestone": str(state.get("current_milestone") or ""),
        "as_of": as_of,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / FROZEN_NAME).write_text(
        json.dumps(frozen, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return frozen


def load_frozen(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / FROZEN_NAME
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def compute_drift(
    project_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    group: str,
    validation_items: dict[str, Any] | None = None,
    drift_max: float = 0.3,
) -> dict[str, Any]:
    frozen = load_frozen(run_dir)
    if not frozen:
        return {
            "drift_score": 0.0,
            "reasons": [],
            "ok": True,
            "reason": "no_frozen",
            "contract": "drift_report_v1",
        }

    group_dir = project_dir / "verification" / stage / group
    check_sha = _sha256_file(group_dir / "CHECK.md")
    manifest_sha = _sha256_file(group_dir / "manifest.yaml")
    cache = load_yaml(project_dir / "cache.yaml")
    current_tag = str((cache.get("tag") or {}).get("value") or "")

    drift = 0.0
    reasons: list[str] = []
    if check_sha != frozen.get("check_sha256"):
        drift = max(drift, 1.0)
        reasons.append("check_md_changed")
    if manifest_sha != frozen.get("manifest_sha256"):
        drift = max(drift, 0.8)
        reasons.append("manifest_changed")
    if current_tag != frozen.get("tag"):
        drift = max(drift, 0.5)
        reasons.append("tag_changed")

    if validation_items:
        failing = int(validation_items.get("failing_count") or 0)
        total = len(validation_items.get("items") or [])
        if total and failing:
            drift = max(drift, round(0.2 * (failing / total), 4))
            reasons.append("goal_items_failing")

    score = round(drift, 4)
    report = {
        "drift_score": score,
        "reasons": reasons,
        "ok": score <= drift_max,
        "drift_max": drift_max,
        "contract": "drift_report_v1",
    }
    (run_dir / DRIFT_NAME).write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def load_drift_report(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / DRIFT_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))