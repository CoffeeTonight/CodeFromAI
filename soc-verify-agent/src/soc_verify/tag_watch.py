"""Git tag watch — fetch latest tag on refresh due (live mode) or touch only (dummy)."""

from __future__ import annotations

import fnmatch
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.config import UserConfig
from soc_verify.models import load_yaml
from soc_verify.tag_cache import apply_tag_replace, should_refresh_tag, touch_tag_refresh


def fetch_latest_tag(git_url: str, tag_pattern: str) -> str | None:
    if not git_url:
        return None
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", git_url],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None

    tags: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.endswith("^{}"):
            continue
        tag = ref.replace("refs/tags/", "")
        if fnmatch.fnmatch(tag, tag_pattern):
            tags.append(tag)
    if not tags:
        return None
    return sorted(tags)[-1]


def refresh_if_due(
    project_dir: Path,
    config: UserConfig,
    *,
    cache: dict[str, Any] | None = None,
    today: date | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    today = today or date.today()
    cache_path = project_dir / "cache.yaml"
    cache = cache if cache is not None else load_yaml(cache_path)

    if not should_refresh_tag(cache, today=today):
        return cache, {"refreshed": False, "reason": "not_due"}

    git_cfg = (config.raw.get("git") or {}) if config else {}
    mode = str(git_cfg.get("mode", "dummy"))
    interval = int(config.tag_refresh_days) if config else 4
    meta: dict[str, Any] = {"refreshed": True, "mode": mode}

    if mode == "live":
        discovered = load_yaml(project_dir / "discovered.yaml")
        git_url = str(discovered.get("git_url") or "")
        tag_pattern = str(git_cfg.get("tag_pattern", "v*"))
        latest = fetch_latest_tag(git_url, tag_pattern) if git_url else None
        current = str((cache.get("tag") or {}).get("value") or "")

        if latest and latest != current:
            updated = apply_tag_replace(
                project_dir,
                latest,
                today=today,
                interval_days=interval,
            )
            meta.update({"tag_changed": True, "new_tag": latest, "old_tag": current})
            return updated, meta

        touch_tag_refresh(project_dir, cache, today=today, interval_days=interval)
        meta["tag_changed"] = False
        return load_yaml(cache_path), meta

    touch_tag_refresh(project_dir, cache, today=today, interval_days=interval)
    meta["tag_changed"] = False
    return load_yaml(cache_path), meta