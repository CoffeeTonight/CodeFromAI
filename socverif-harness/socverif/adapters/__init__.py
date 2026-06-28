"""Environment adapter registry — project-specific logic stays out of core."""
# goal_build_id = 12

from pathlib import Path
from typing import Any

from socverif.adapters.base import EnvironmentAdapter, TierSpec
from socverif.adapters.registry import get_adapters, reset_cache


def select_adapter(root, scan_context: dict | None = None) -> EnvironmentAdapter:
    root = Path(root).resolve()
    for adapter in get_adapters(root):
        if adapter.id == "generic":
            continue
        if adapter.detect(root, scan_context or {}):
            return adapter
    for adapter in get_adapters(root):
        if adapter.id == "generic":
            return adapter
    from socverif.adapters.generic import GenericAdapter
    return GenericAdapter()


def apply_adapters(root, manifest: dict) -> dict:
    adapter = select_adapter(root, manifest)
    manifest["adapter"] = {"id": adapter.id, "name": adapter.name}
    return adapter.enrich_manifest(root, manifest)


__all__ = ["EnvironmentAdapter", "TierSpec", "select_adapter", "apply_adapters", "get_adapters", "reset_cache"]