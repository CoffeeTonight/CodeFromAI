"""Bootstrap paper-oriented intake skill templates into project skills + Obsidian mirror."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml
from soc_verify.obsidian_md import LAYER_SKILLS, wikilink
from soc_verify.skill_registry import register_skill


SPEC_NAME = "paper_intake_skills_spec.yaml"
SKILL_FILE = "SKILL.md"


def load_spec(root: Path) -> dict[str, Any]:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = _repo_root() / "registry" / SPEC_NAME
    return load_yaml(p) or {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def template_dir(root: Path) -> Path:
    spec = load_spec(root)
    rel = str(spec.get("template_dir", "templates/skills/paper-intake"))
    cand = root / rel
    if cand.is_dir():
        return cand
    bundled = _repo_root() / rel
    return bundled if bundled.is_dir() else cand


def list_paper_intake_skill_ids(root: Path) -> list[str]:
    spec = load_spec(root)
    return [str(s.get("id", "")) for s in spec.get("skills") or [] if s.get("id")]


def read_template_skill(root: Path, skill_id: str) -> str:
    path = template_dir(root) / skill_id / SKILL_FILE
    if not path.is_file():
        raise FileNotFoundError(f"paper intake skill template not found: {path}")
    return path.read_text(encoding="utf-8")


def collect_paper_skills_for_llm(project_dir: Path, root: Path) -> list[dict[str, Any]]:
    """Skills to inject into intake/normalize LLM prompts (read order from spec)."""
    spec = load_spec(root)
    order = list(spec.get("llm_read_order") or [])
    if not order:
        order = list_paper_intake_skill_ids(root)

    out: list[dict[str, Any]] = []
    for sid in order:
        skill_path = project_dir / "skills" / sid / SKILL_FILE
        if skill_path.is_file():
            body = skill_path.read_text(encoding="utf-8")
        else:
            try:
                body = read_template_skill(root, sid)
            except FileNotFoundError:
                continue
        out.append(
            {
                "id": sid,
                "path": str(skill_path.relative_to(project_dir)) if skill_path.is_file() else f"skills/{sid}/{SKILL_FILE}",
                "body": body[:12000],
            }
        )
    return out


def _mirror_obsidian_skill(project_dir: Path, skill_id: str, body: str) -> Path:
    obs_dir = project_dir / "knowledge" / "obsidian" / LAYER_SKILLS
    obs_dir.mkdir(parents=True, exist_ok=True)
    note = obs_dir / f"{skill_id}.md"
    header = f"""---
type: skill
skill_id: {skill_id}
ast_layer: {LAYER_SKILLS}
tags: [paper, intake]
mirrored_from: skills/{skill_id}/{SKILL_FILE}
---

"""
    if body.lstrip().startswith("---"):
        note.write_text(body, encoding="utf-8")
    else:
        note.write_text(header + body.strip() + "\n", encoding="utf-8")
    return note


def bootstrap_paper_intake_skills(
    project_dir: Path,
    root: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Install platform paper-intake SKILL.md set into project + 04-skills Obsidian mirror."""
    root = root.resolve()
    spec = load_spec(root)
    tags = list((spec.get("bootstrap") or {}).get("tags") or ["paper", "intake"])
    registered: list[str] = []
    mirrored: list[str] = []

    for block in sorted(spec.get("skills") or [], key=lambda x: int(x.get("order", 99))):
        if not isinstance(block, dict):
            continue
        sid = str(block.get("id", ""))
        if not sid:
            continue
        name = str(block.get("name", sid))
        body = read_template_skill(root, sid)
        skill_file = project_dir / "skills" / sid / SKILL_FILE
        if skill_file.is_file() and not force:
            existing = skill_file.read_text(encoding="utf-8")
            if existing.strip() == body.strip():
                mirrored.append(str(_mirror_obsidian_skill(project_dir, sid, existing).relative_to(project_dir)))
                registered.append(sid)
                continue

        register_skill(
            project_dir,
            name=name,
            body=body,
            skill_id=sid,
            milestone_ids=[],
            tags=tags + [str(block.get("role", ""))],
            source="paper_intake_bootstrap",
        )
        registered.append(sid)
        mirrored.append(str(_mirror_obsidian_skill(project_dir, sid, body).relative_to(project_dir)))

    manifest = {
        "contract": "paper_intake_skills_manifest_v1",
        "project_id": project_dir.name,
        "bootstrapped_at": datetime.now(timezone.utc).isoformat(),
        "skill_ids": registered,
        "primary_skill": spec.get("primary_skill", "paper-intake-curate"),
        "hub_skill": spec.get("hub_skill", "paper-intake-hub"),
        "obsidian_mirror": mirrored,
        "llm_read_order": spec.get("llm_read_order", registered),
    }
    manifest_path = project_dir / "intake" / "paper_intake_skills.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "count": len(registered),
        "skill_ids": registered,
        "manifest": str(manifest_path.relative_to(project_dir)),
        "hub_wikilink": wikilink(LAYER_SKILLS, str(spec.get("hub_skill", "paper-intake-hub"))),
    }


def paper_skills_prompt_block(project_dir: Path, root: Path) -> dict[str, Any]:
    """Compact block for LLM intake/normalize prompts."""
    spec = load_spec(root)
    skills = collect_paper_skills_for_llm(project_dir, root)
    primary = str(spec.get("primary_skill", "paper-intake-curate"))
    primary_body = next((s["body"] for s in skills if s["id"] == primary), "")
    return {
        "task_context": "paper_publication_intake",
        "primary_skill": primary,
        "hub_skill": spec.get("hub_skill"),
        "skill_paths": [s["path"] for s in skills],
        "primary_skill_excerpt": primary_body[:8000],
        "instruction": (
            "Curate all intake sources to publication grade per primary_skill. "
            "Every numeric claim needs source_ref. Map evidence to paper sections. "
            "Record gaps in 05-intake/intake.json paper_curation field."
        ),
    }