"""Register a thin project from discovered.yaml or clone path for detect."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml
from soc_verify.toy_intake import DEFAULT_ROOT_MARKER, slug_toy_project_id


def register_project_from_discovered(
    root: Path,
    discovered_file: Path,
    *,
    project_id: str = "",
) -> dict[str, Any]:
    """Write projects/{id} skeleton from a discovered.yaml path. Returns project_id."""
    root = root.resolve()
    discovered_file = discovered_file.expanduser().resolve()
    if not discovered_file.is_file():
        raise FileNotFoundError(f"discovered file not found: {discovered_file}")
    raw = load_yaml(discovered_file) or {}
    pid = (project_id or str(raw.get("project_id") or raw.get("id") or "")).strip()
    if not pid:
        raise ValueError("discovered.yaml needs project_id or pass --project")
    pid = pid if pid.startswith("OSS-") or "-" in pid else pid

    local = str(raw.get("local_clone_path") or "").strip()
    if not local:
        raise ValueError("discovered.yaml needs local_clone_path")

    today = date.today().isoformat()
    pdir = root / "projects" / pid
    pdir.mkdir(parents=True, exist_ok=True)

    data = {
        "project_id": pid,
        "source": raw.get("source") or "onboard_discovered",
        "title": raw.get("title") or pid,
        "git_url": raw.get("git_url") or "",
        "local_clone_path": str(Path(local).expanduser()),
        "rtl_subdir": str(raw.get("rtl_subdir") or ""),
        "root_marker": str(raw.get("root_marker") or DEFAULT_ROOT_MARKER),
        "required_artifacts": list(raw.get("required_artifacts") or []),
        "doc_rev": str(raw.get("doc_rev") or "r1.0"),
        "doc_path": str(raw.get("doc_path") or f"oss/{pid}"),
        "current_milestone": str(raw.get("current_milestone") or "M1"),
        "intake": {
            "fetched_at": today,
            "source": "onboard_discovered",
            "from_file": str(discovered_file),
        },
    }
    save_yaml(pdir / "discovered.yaml", data)
    save_yaml(
        pdir / "meta.yaml",
        {
            "project_id": pid,
            "discovered_from": "discovered.yaml",
            "environment_profile": "onboard",
            "sync": {"fetched_at": today, "source": ["discovered.yaml"]},
        },
    )
    save_yaml(
        pdir / "state.yaml",
        {
            "as_of": today,
            "active": True,
            "schedule_plan": "onboard-v1",
            "current_milestone": data["current_milestone"],
            "sync": {"fetched_at": today, "source": "intake"},
            "environment_profile": "onboard",
        },
    )
    save_yaml(
        pdir / "cache.yaml",
        {
            "tag": {"value": "main", "fetched_at": today},
            "clone": {
                "path": str(Path(local).expanduser()),
                "valid_for_tag": "main",
                "fetched_at": today,
            },
        },
    )
    return {"project_id": pid, "project_dir": str(pdir), "discovered": data}


def register_project_from_clone(
    root: Path,
    *,
    project_id: str,
    local_clone_path: str,
    rtl_subdir: str = "",
    root_marker: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Minimal discovered for a bare OSS clone path."""
    root = root.resolve()
    clone = Path(local_clone_path).expanduser().resolve()
    if not clone.is_dir():
        raise FileNotFoundError(f"clone path not found: {clone}")
    rtl = clone / rtl_subdir if rtl_subdir else clone
    marker = root_marker
    if not marker:
        for cand in ("example.sh", "Makefile", "README.md", "README"):
            if (rtl / cand).is_file():
                marker = cand
                break
    if not marker:
        raise ValueError(f"no root_marker found under {rtl}")

    tmp = root / "projects" / "_onboard_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    disc = tmp / f"{project_id}.discovered.yaml"
    save_yaml(
        disc,
        {
            "project_id": project_id,
            "title": title or project_id,
            "local_clone_path": str(clone),
            "rtl_subdir": rtl_subdir,
            "root_marker": marker,
            "source": "onboard_clone",
        },
    )
    return register_project_from_discovered(root, disc, project_id=project_id)
