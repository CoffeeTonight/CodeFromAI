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


def unified_verify_dir() -> Path:
    """design/unified_verify (replaces legacy HDLforAST)."""
    return design_dir("unified_verify")


def hfa_rtl_dir() -> Path:
    """RTL formerly under design/HDLforAST."""
    return unified_verify_dir() / "rtl" / "hfa"


def unified_filelist() -> Path:
    return unified_verify_dir() / "filelist.f"


def unified_top_module_filelist() -> Path:
    """hfa-only filelist (legacy HDLforAST behavior)."""
    return unified_verify_dir() / "filelist_top_module.f"