"""RTL root resolution — toy scaffold."""

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
    raise FileNotFoundError("cache.yaml clone.path or discovered local_clone_path required")


def resolve_rtl_root(project_dir: Path, *, tag: str | None = None) -> Path:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    gate = load_yaml(project_dir / "meta" / "toy_gate.yaml") or {}
    marker = str(gate.get("root_marker") or discovered.get("root_marker") or "example.sh")
    clone = _clone_root(project_dir)
    clone_path = Path(str(clone))
    sub = str(discovered.get("rtl_subdir") or "").strip()
    if not clone_path.is_dir():
        raise FileNotFoundError(f"clone path not found: {clone_path}")
    root = clone_path / sub if sub else clone_path
    if not (root / marker).is_file():
        raise FileNotFoundError(f"RTL root not found (no {marker}): {root}")
    return root.resolve()
