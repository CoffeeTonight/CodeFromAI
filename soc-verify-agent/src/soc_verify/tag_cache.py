"""Tag sticky cache + mandatory replace on new tag."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from soc_verify.constants import DEFAULT_TAG_REFRESH_DAYS
from soc_verify.models import load_yaml, save_yaml


def _parse_date(s: str) -> date:
    return date.fromisoformat(s[:10])


def should_refresh_tag(cache: dict[str, Any], today: date | None = None) -> bool:
    today = today or date.today()
    tag_block = cache.get("tag") or {}
    policy = tag_block.get("refresh_policy") or {}
    next_refresh = tag_block.get("next_refresh") or policy.get("next_refresh")
    if next_refresh is None or next_refresh == "":
        return True
    return today >= _parse_date(str(next_refresh))


def apply_tag_replace(
    project_dir: Path,
    new_tag: str,
    *,
    clone_path: str | None = None,
    today: date | None = None,
    interval_days: int = DEFAULT_TAG_REFRESH_DAYS,
) -> dict[str, Any]:
    """New tag → always replace. Cascade-invalidate dependent cache."""
    today = today or date.today()
    cache_path = project_dir / "cache.yaml"
    cache = load_yaml(cache_path)
    old_tag = (cache.get("tag") or {}).get("value", "")

    if clone_path is None:
        clone_path = str(project_dir / "workspace" / new_tag)

    cache["tag"] = {
        "value": new_tag,
        "fetched_at": today.isoformat(),
        "refresh_policy": {
            "interval_days": interval_days,
            "next_refresh": (today + timedelta(days=interval_days)).isoformat(),
        },
        "replace_decision": "replace" if new_tag != old_tag else "keep",
        "previous_tag": old_tag,
    }

    cache["clone"] = {
        "path": clone_path,
        "valid_for_tag": new_tag,
        "fetched_at": today.isoformat(),
    }

    # Cascade invalidation
    cache["sanity"] = {
        "last_verdict": None,
        "last_run": None,
        "valid_for_tag": new_tag,
    }

    invalidated_groups: list[str] = []
    for key, val in list(cache.get("group_results", {}).items()):
        if isinstance(val, dict) and val.get("valid_for_tag") != new_tag:
            invalidated_groups.append(key)
    for key in invalidated_groups:
        cache.setdefault("group_results", {}).pop(key, None)

    cache["on_tag_replace"] = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "old_tag": old_tag,
        "new_tag": new_tag,
        "invalidated": {
            "sanity": True,
            "group_results": invalidated_groups,
        },
    }

    save_yaml(cache_path, cache)

    # Demote tag-tied trust records
    trust_path = project_dir / "trust" / "registry.yaml"
    trust = load_yaml(trust_path)
    for name, rec in (trust.get("scripts") or {}).items():
        if isinstance(rec, dict) and rec.get("tied_to_tag") and rec.get("status") == "canonical":
            rec["status"] = "evaluated"
            rec["demote_reason"] = f"tag_replace:{old_tag}->{new_tag}"
    if trust:
        save_yaml(trust_path, trust)

    return cache