"""Thin VerifCPU RTL root resolution for VERIF-TOY-SOC."""

from __future__ import annotations

from pathlib import Path

from soc_verify.models import load_yaml


def _clone_root(project_dir: Path) -> str:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    cache = load_yaml(project_dir / "cache.yaml") or {}
    clone = (cache.get("clone") or {}).get("path")
    if clone:
        return str(clone)
    local = str(discovered.get("local_clone_path") or "").strip()
    if local:
        return str(Path(local).expanduser())
    raise FileNotFoundError(
        "cache.yaml missing clone.path — set discovered.yaml local_clone_path"
    )


def resolve_rtl_root(project_dir: Path, *, tag: str | None = None) -> Path:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    clone = _clone_root(project_dir)
    clone_path = Path(str(clone))
    sub = str(discovered.get("rtl_subdir") or "").strip()
    if not clone_path.is_dir():
        cfa_root = project_dir.resolve().parents[2]
        fallback = cfa_root / sub if sub else cfa_root
        if (fallback / "example.sh").is_file():
            return fallback
        raise FileNotFoundError(f"clone path not found: {clone_path}")
    root = clone_path / sub if sub else clone_path
    if not (root / "example.sh").is_file():
        raise FileNotFoundError(f"VerifCPU root not found (no example.sh): {root}")
    return root