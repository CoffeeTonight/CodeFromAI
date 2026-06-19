"""Scheduled knowledge intake (Confluence/wiki/md) — orchestrator acquisition."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.acquisition import stamp_refresh_policy
from soc_verify.config import UserConfig
from soc_verify.models import load_yaml, save_yaml


SYNC_NAME = "knowledge_sync.yaml"


def knowledge_sync_path(project_dir: Path) -> Path:
    return project_dir / "intake" / SYNC_NAME


def load_knowledge_sync(project_dir: Path) -> dict[str, Any]:
    path = knowledge_sync_path(project_dir)
    if not path.is_file():
        return {"contract": "knowledge_sync_v1", "project_id": project_dir.name}
    data = load_yaml(path)
    return data if isinstance(data, dict) else {"contract": "knowledge_sync_v1"}


def save_knowledge_sync(project_dir: Path, data: dict[str, Any]) -> Path:
    path = knowledge_sync_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("contract", "knowledge_sync_v1")
    data.setdefault("project_id", project_dir.name)
    save_yaml(path, data)
    return path


def refresh_knowledge_collect(
    root: Path,
    project_dir: Path,
    config: UserConfig,
    today: date | None = None,
    *,
    normalize: bool = False,
) -> dict[str, Any]:
    """Collect Confluence/wiki/md → bundle + 05-intake; stamp knowledge_sync schedule."""
    from soc_verify.knowledge_intake import collect_knowledge_bundle, normalize_to_obsidian

    today = today or date.today()
    days = config.knowledge_collect_days
    pid = project_dir.name

    bundle = collect_knowledge_bundle(root, pid)
    result: dict[str, Any] = {
        "project_id": pid,
        "sources": len(bundle.get("sources") or []),
        "bundle": "intake/knowledge_bundle.json",
        "collected_at": bundle.get("collected_at"),
    }

    if normalize:
        norm = normalize_to_obsidian(root, pid)
        result["normalize"] = {"ok": norm.get("ok"), "stub": norm.get("stub")}

    stamp = stamp_refresh_policy(today, days)
    sync = {
        **load_knowledge_sync(project_dir),
        **stamp,
        "source": "knowledge_collect",
        "last_collect": result,
    }
    save_knowledge_sync(project_dir, sync)
    return {**stamp, "last_collect": result}