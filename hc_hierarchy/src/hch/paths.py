"""Design paths relative to hc_hierarchy project root."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def design_dir(name: str) -> Path:
    """Resolve design/<name>, with fallback to sibling repo layout."""
    primary = PROJECT_ROOT / "design" / name
    if primary.exists():
        return primary
    fallback = PROJECT_ROOT.parent / "design" / name
    return fallback if fallback.exists() else primary