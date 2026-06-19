"""Platform lifecycle — first-start detection and cumulative per-use telemetry."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml


BASELINE_NAME = "platform_baseline.yaml"
TELEMETRY_NAME = "platform_telemetry.yaml"
CODE_CHANGES_NAME = "code_change_log.yaml"


def _registry_dir(root: Path) -> Path:
    d = root / "registry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def baseline_path(root: Path) -> Path:
    return _registry_dir(root) / BASELINE_NAME


def telemetry_path(root: Path) -> Path:
    return _registry_dir(root) / TELEMETRY_NAME


def code_changes_path(root: Path) -> Path:
    return _registry_dir(root) / CODE_CHANGES_NAME


def ensure_platform_baseline(root: Path, *, trigger: str = "cli") -> dict[str, Any]:
    """Detect first tool start; create baseline marker if absent."""
    path = baseline_path(root)
    data = load_yaml(path)
    now = datetime.now(timezone.utc).isoformat()
    if data and data.get("first_started_at"):
        data["last_touch_at"] = now
        data["last_trigger"] = trigger
        data["use_count"] = int(data.get("use_count", 0)) + 1
        save_yaml(path, data)
        return data

    data = {
        "contract": "platform_baseline_v1",
        "first_started_at": now,
        "first_trigger": trigger,
        "last_touch_at": now,
        "last_trigger": trigger,
        "use_count": 1,
        "note": "Baseline established — all subsequent uses append to platform_telemetry.yaml",
    }
    save_yaml(path, data)

    tel = load_yaml(telemetry_path(root))
    if not tel:
        save_yaml(
            telemetry_path(root),
            {
                "contract": "platform_telemetry_v1",
                "baseline_at": now,
                "uses": [],
                "cumulative": {
                    "total_uses": 0,
                    "verify_runs": 0,
                    "orchestrator_runs": 0,
                    "pass_count": 0,
                    "fail_count": 0,
                    "success_rate": 0.0,
                    "trust_samples": [],
                    "code_edit_count": 0,
                },
            },
        )
    return data


def record_code_change(
    root: Path,
    *,
    run_id: str,
    project_id: str,
    layer: str,
    target: str,
    rationale: str,
    source: str,
    applied: bool = False,
) -> None:
    path = code_changes_path(root)
    data = load_yaml(path)
    if not data:
        data = {"contract": "code_change_log_v1", "changes": []}
    changes = list(data.get("changes") or [])
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "date": date.today().isoformat(),
        "run_id": run_id,
        "project_id": project_id,
        "layer": layer,
        "target": target,
        "rationale": rationale,
        "source": source,
        "applied": applied,
    }
    changes.append(entry)
    if len(changes) > 5000:
        changes = changes[-5000:]
    data["changes"] = changes
    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)

    _bump_code_edit_count(root)


def _bump_code_edit_count(root: Path) -> None:
    tel_path = telemetry_path(root)
    tel = load_yaml(tel_path) or {}
    cum = tel.setdefault("cumulative", {})
    cum["code_edit_count"] = int(cum.get("code_edit_count", 0)) + 1
    save_yaml(tel_path, tel)


def record_platform_use(
    root: Path,
    *,
    kind: str,
    run_id: str,
    verdict: str,
    trust_score: float | None = None,
    trust_delta: float | None = None,
    success_rate: float | None = None,
    project_id: str = "",
    stage: str = "",
    group: str = "",
    graph_id: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one use record since baseline — success/trust/code-edit context."""
    ensure_platform_baseline(root, trigger=kind)
    path = telemetry_path(root)
    data = load_yaml(path) or {"contract": "platform_telemetry_v1", "uses": [], "cumulative": {}}
    uses = list(data.get("uses") or [])

    prev_trust = None
    if uses:
        prev_trust = uses[-1].get("trust_score")

    if trust_delta is None and trust_score is not None and prev_trust is not None:
        trust_delta = round(float(trust_score) - float(prev_trust), 4)

    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "date": date.today().isoformat(),
        "kind": kind,
        "graph_id": graph_id,
        "run_id": run_id,
        "project_id": project_id,
        "stage": stage,
        "group": group,
        "verdict": verdict,
        "success": verdict == "PASS",
        "trust_score": trust_score,
        "trust_delta": trust_delta,
        "success_rate": success_rate,
        "extra": extra or {},
    }
    uses.append(entry)
    if len(uses) > 2000:
        uses = uses[-2000:]
    data["uses"] = uses

    cum = data.setdefault("cumulative", {})
    cum["total_uses"] = int(cum.get("total_uses", 0)) + 1
    if graph_id == "orchestrator" or kind.startswith("orchestrator"):
        cum["orchestrator_runs"] = int(cum.get("orchestrator_runs", 0)) + 1
    else:
        cum["verify_runs"] = int(cum.get("verify_runs", 0)) + 1
    if verdict == "PASS":
        cum["pass_count"] = int(cum.get("pass_count", 0)) + 1
    else:
        cum["fail_count"] = int(cum.get("fail_count", 0)) + 1
    total = int(cum.get("pass_count", 0)) + int(cum.get("fail_count", 0))
    cum["success_rate"] = round(int(cum.get("pass_count", 0)) / max(1, total), 4)

    if trust_score is not None:
        samples = list(cum.get("trust_samples") or [])
        samples.append({"run_id": run_id, "trust": trust_score, "delta": trust_delta})
        if len(samples) > 500:
            samples = samples[-500:]
        cum["trust_samples"] = samples

    data["last_updated"] = date.today().isoformat()
    save_yaml(path, data)
    return entry


def load_cumulative_stats(root: Path) -> dict[str, Any]:
    ensure_platform_baseline(root, trigger="read")
    data = load_yaml(telemetry_path(root)) or {}
    return dict(data.get("cumulative") or {})


def code_change_summary(root: Path, *, since_baseline: bool = True) -> dict[str, Any]:
    data = load_yaml(code_changes_path(root)) or {}
    changes = list(data.get("changes") or [])
    by_layer: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for ch in changes:
        layer = str(ch.get("layer", "unknown"))
        source = str(ch.get("source", "unknown"))
        by_layer[layer] = by_layer.get(layer, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1
    return {
        "total": len(changes),
        "by_layer": by_layer,
        "by_source": by_source,
        "recent": changes[-10:],
    }