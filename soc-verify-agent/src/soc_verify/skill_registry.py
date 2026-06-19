"""Project-scoped verification skill registry — store, retrieve, maintain user skillsets."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml

REGISTRY_NAME = "registry.yaml"
SKILL_FILE = "SKILL.md"


def skills_root(project_dir: Path) -> Path:
    return project_dir / "skills"


def registry_path(project_dir: Path) -> Path:
    return skills_root(project_dir) / REGISTRY_NAME


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower())
    return s.strip("-") or "skill"


def load_registry(project_dir: Path) -> dict[str, Any]:
    path = registry_path(project_dir)
    if not path.is_file():
        return {
            "contract": "skill_registry_v1",
            "project_id": project_dir.name,
            "skills": [],
            "updated_at": "",
        }
    data = load_yaml(path)
    if not isinstance(data, dict):
        return {"contract": "skill_registry_v1", "project_id": project_dir.name, "skills": []}
    data.setdefault("skills", [])
    data.setdefault("project_id", project_dir.name)
    return data


def save_registry(project_dir: Path, registry: dict[str, Any]) -> Path:
    root = skills_root(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    registry.setdefault("project_id", project_dir.name)
    path = registry_path(project_dir)
    save_yaml(path, registry)
    return path


def _find_skill(registry: dict[str, Any], skill_id: str) -> dict[str, Any] | None:
    for sk in registry.get("skills") or []:
        if isinstance(sk, dict) and str(sk.get("id")) == skill_id:
            return sk
    return None


def list_skills(project_dir: Path, *, milestone: str = "") -> list[dict[str, Any]]:
    registry = load_registry(project_dir)
    skills = [s for s in registry.get("skills") or [] if isinstance(s, dict)]
    if not milestone:
        return skills
    mid = milestone.strip()
    return [
        s
        for s in skills
        if mid in (s.get("milestone_ids") or []) or not s.get("milestone_ids")
    ]


def get_skill(project_dir: Path, skill_id: str) -> dict[str, Any] | None:
    registry = load_registry(project_dir)
    entry = _find_skill(registry, skill_id)
    if not entry:
        return None
    skill_path = project_dir / str(entry.get("path", ""))
    body = ""
    if skill_path.is_file():
        body = skill_path.read_text(encoding="utf-8")
    return {**entry, "body": body}


def register_skill(
    project_dir: Path,
    *,
    name: str,
    body: str,
    skill_id: str = "",
    milestone_ids: list[str] | None = None,
    tags: list[str] | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Register or update a verification skill under projects/{id}/skills/."""
    sid = skill_id or _slug(name)
    root = skills_root(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    rel = f"skills/{sid}/{SKILL_FILE}"
    skill_dir = project_dir / "skills" / sid
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / SKILL_FILE
    skill_file.write_text(body.strip() + "\n", encoding="utf-8")

    registry = load_registry(project_dir)
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": sid,
        "name": name,
        "path": rel,
        "milestone_ids": list(milestone_ids or []),
        "tags": list(tags or []),
        "source": source,
        "updated_at": now,
    }
    existing = _find_skill(registry, sid)
    if existing:
        existing.update(entry)
    else:
        entry["created_at"] = now
        registry.setdefault("skills", []).append(entry)
    save_registry(project_dir, registry)
    return entry


def register_skillset_from_text(
    project_dir: Path,
    text: str,
    *,
    default_milestone: str = "",
    source: str = "user_intake",
) -> list[dict[str, Any]]:
    """Parse free-form skillset text into registry entries (one per non-empty block)."""
    text = (text or "").strip()
    if not text:
        return []

    intake_path = skills_root(project_dir) / "intake.md"
    intake_path.parent.mkdir(parents=True, exist_ok=True)
    intake_path.write_text(text + "\n", encoding="utf-8")

    blocks = [b.strip() for b in re.split(r"\n---+\n|\n\n(?=#)", text) if b.strip()]
    if len(blocks) == 1 and "\n" in blocks[0]:
        lines = [ln.strip() for ln in blocks[0].splitlines() if ln.strip()]
        if all(len(ln) < 120 and not ln.startswith("#") for ln in lines) and len(lines) > 1:
            blocks = lines

    registered: list[dict[str, Any]] = []
    for block in blocks:
        first_line = block.splitlines()[0].strip()
        if first_line.startswith("#"):
            name = first_line.lstrip("#").strip()
            body = block
        else:
            name = first_line[:80]
            body = f"# {name}\n\n{block}" if not block.startswith("#") else block
        mids = [default_milestone] if default_milestone else []
        entry = register_skill(
            project_dir,
            name=name,
            body=body,
            milestone_ids=mids,
            source=source,
        )
        registered.append(entry)
    return registered


def update_skill(
    project_dir: Path,
    skill_id: str,
    *,
    name: str | None = None,
    body: str | None = None,
    milestone_ids: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    registry = load_registry(project_dir)
    entry = _find_skill(registry, skill_id)
    if not entry:
        return None
    if name:
        entry["name"] = name
    if milestone_ids is not None:
        entry["milestone_ids"] = list(milestone_ids)
    if tags is not None:
        entry["tags"] = list(tags)
    if body is not None:
        path = project_dir / str(entry.get("path", f"skills/{skill_id}/{SKILL_FILE}"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body.strip() + "\n", encoding="utf-8")
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(project_dir, registry)
    return entry


def delete_skill(project_dir: Path, skill_id: str) -> bool:
    registry = load_registry(project_dir)
    skills = registry.get("skills") or []
    kept = [s for s in skills if isinstance(s, dict) and str(s.get("id")) != skill_id]
    if len(kept) == len(skills):
        return False
    registry["skills"] = kept
    save_registry(project_dir, registry)
    skill_dir = skills_root(project_dir) / skill_id
    if skill_dir.is_dir():
        for f in skill_dir.iterdir():
            f.unlink(missing_ok=True)
        skill_dir.rmdir()
    return True