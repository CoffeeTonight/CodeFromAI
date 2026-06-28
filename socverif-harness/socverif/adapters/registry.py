"""Pluggable adapter registry — generic adapter is always last (universal fallback)."""
# goal_build_id = 12

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from socverif.adapters.base import EnvironmentAdapter

_BUILTIN_ORDER = (
    "socverif.adapters.verifcpu:VerifCpuAdapter",
    "socverif.adapters.generic:GenericAdapter",
)

_CACHE: list[EnvironmentAdapter] | None = None


def _load_class(spec: str) -> EnvironmentAdapter:
    module_path, class_name = spec.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls()


def _from_entry_points() -> list[EnvironmentAdapter]:
    adapters: list[EnvironmentAdapter] = []
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="socverif.adapters")
        for ep in eps:
            try:
                adapters.append(ep.load()())
            except Exception:
                continue
    except Exception:
        pass
    return adapters


def _from_plugin_dir(root: Path | None) -> list[EnvironmentAdapter]:
    if root is None:
        return []
    plugin_dir = root / ".socverif" / "adapters"
    if not plugin_dir.is_dir():
        return []
    adapters: list[EnvironmentAdapter] = []
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    for py in sorted(plugin_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(py.stem)
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and hasattr(obj, "detect") and hasattr(obj, "enrich_manifest"):
                    adapters.append(obj())
                    break
        except Exception:
            continue
    return adapters


def get_adapters(project_root: Path | None = None) -> list[EnvironmentAdapter]:
    global _CACHE
    if _CACHE is not None and project_root is None:
        return _CACHE

    seen: set[str] = set()
    ordered: list[EnvironmentAdapter] = []

    for ep_ad in _from_entry_points():
        if ep_ad.id not in seen:
            seen.add(ep_ad.id)
            ordered.append(ep_ad)

    for spec in _BUILTIN_ORDER:
        try:
            ad = _load_class(spec)
            if ad.id not in seen:
                seen.add(ad.id)
                ordered.append(ad)
        except Exception:
            continue

    for plug in _from_plugin_dir(project_root):
        if plug.id not in seen:
            seen.add(plug.id)
            ordered.insert(-1, plug)  # before generic fallback

    # generic must be last
    ordered.sort(key=lambda a: 1 if a.id == "generic" else 0)
    if project_root is None:
        _CACHE = ordered
    return ordered


def reset_cache() -> None:
    global _CACHE
    _CACHE = None