"""Design paths relative to hc_hierarchy project root."""

from __future__ import annotations

from pathlib import Path

from hch.platform_paths import (  # noqa: F401 — re-export
    path_to_db,
    path_to_posix,
    path_to_slang,
    paths_equal,
    resolve_path,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def design_dir(name: str) -> Path:
    """Resolve design/<name>, with fallback to sibling repo layout."""
    primary = PROJECT_ROOT / "design" / name
    if primary.exists():
        return primary
    fallback = PROJECT_ROOT.parent / "design" / name
    return fallback if fallback.exists() else primary