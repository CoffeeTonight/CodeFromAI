"""Platform acquisition refresh stubs (dummy Confluence). Updates fetched_at deterministically."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.acquisition import stamp_refresh_policy
from soc_verify.config import UserConfig
from soc_verify.models import load_yaml, save_yaml


def _today(today: date | None) -> date:
    return today or date.today()


def refresh_project_search(root: Path, config: UserConfig, today: date | None = None) -> dict[str, Any]:
    """Re-materialize active_projects from dummy snapshot when Confluence unavailable."""
    today = _today(today)
    days = config.project_search_days
    registry_path = root / "registry" / "active_projects.yaml"
    registry = load_yaml(registry_path)

    snapshot_path = root / "platform" / "intake" / "dummy_confluence_snapshot.yaml"
    if snapshot_path.is_file():
        snap = load_yaml(snapshot_path)
        projects = []
        for p in snap.get("projects", []):
            if not isinstance(p, dict):
                continue
            projects.append(
                {
                    "id": p["id"],
                    "active": p.get("status") != "completed",
                    "status": p.get("status", "in_progress"),
                    "current_milestone": p.get("current_milestone"),
                    **({"completed_at": p["completed_at"]} if p.get("completed_at") else {}),
                }
            )
        registry["projects"] = projects
        registry["source"] = snap.get("source", "dummy_confluence_snapshot")
        from soc_verify.milestone_plans import default_plan_id

        registry["schedule_plan"] = default_plan_id(root)

    stamp = stamp_refresh_policy(today, days)
    registry["as_of"] = today.isoformat()
    registry.setdefault("acquisition", {})["project_search"] = {
        **stamp,
        "source": registry.get("source", "project_search"),
    }
    save_yaml(registry_path, registry)
    return registry["acquisition"]["project_search"]


def refresh_project_intake(project_dir: Path, config: UserConfig, today: date | None = None) -> dict[str, Any]:
    today = _today(today)
    days = config.project_intake_days
    path = project_dir / "discovered.yaml"
    data = load_yaml(path)
    stamp = stamp_refresh_policy(today, days)
    data["intake"] = {
        **stamp,
        "source": data.get("source", "intake"),
    }
    save_yaml(path, data)
    return data["intake"]


def refresh_state_sync(project_dir: Path, config: UserConfig, today: date | None = None) -> dict[str, Any]:
    today = _today(today)
    days = config.project_intake_days
    path = project_dir / "state.yaml"
    data = load_yaml(path)
    stamp = stamp_refresh_policy(today, days)
    data["as_of"] = today.isoformat()
    data["sync"] = {
        **stamp,
        "source": "intake",
    }
    save_yaml(path, data)

    meta_path = project_dir / "meta.yaml"
    if meta_path.is_file():
        meta = load_yaml(meta_path)
        meta["sync"] = {"fetched_at": today.isoformat(), "source": ["discovered.yaml", "state.yaml"]}
        save_yaml(meta_path, meta)

    return data["sync"]