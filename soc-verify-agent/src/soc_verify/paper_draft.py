"""Paper draft — TUI/LLM prompt builder and optional draft generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.paper_readiness import assess_paper_readiness, format_readiness_summary


def default_campaign(root: Path, answers: dict[str, Any] | None = None) -> str:
    if answers and answers.get("paper_campaign"):
        return str(answers["paper_campaign"])
    cfg_path = root / "config.json"
    if cfg_path.is_file():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        camp = (cfg.get("paper") or {}).get("default_campaign")
        if camp:
            return str(camp)
    return "paper_eval_2026"


def build_paper_draft_prompt(
    root: Path,
    project_id: str,
    campaign: str,
    *,
    language: str = "ko",
) -> dict[str, Any]:
    root = root.resolve()
    project_dir = root / "projects" / project_id
    readiness = assess_paper_readiness(root, campaign)

    progress_json = project_dir / "knowledge" / "obsidian" / "06-paper" / "paper_progress.json"
    progress_md = project_dir / "knowledge" / "obsidian" / "06-paper" / "PROGRESS.md"
    export_dir = root / "exports" / campaign

    artifacts: dict[str, str] = {
        "progress_md": str(progress_md.relative_to(root)) if progress_md.is_file() else "",
        "progress_json": str(progress_json.relative_to(root)) if progress_json.is_file() else "",
        "sources_moc": f"projects/{project_id}/knowledge/obsidian/05-intake/SOURCES-MOC.md",
        "intake_json": f"projects/{project_id}/knowledge/obsidian/05-intake/intake.json",
        "paper_skills": f"projects/{project_id}/skills/paper-intake-curate/SKILL.md",
        "langgraph_summary": "templates/obsidian/11-LANGGRAPH-SUMMARY.md",
    }
    if export_dir.is_dir():
        for name in ("runs.csv", "methods.md", "methods.json", "paper_readiness.json"):
            p = export_dir / name
            if p.is_file():
                artifacts[f"export_{name.replace('.', '_')}"] = str(p.relative_to(root))

    writable = [s for s in readiness.get("section_status") or [] if s.get("writable")]
    blocked = [s for s in readiness.get("section_status") or [] if not s.get("writable")]

    return {
        "contract": "paper_draft_prompt_v1",
        "task": "write_paper_draft",
        "project_id": project_id,
        "campaign": campaign,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "readiness": {
            "overall_percent": readiness.get("overall_percent"),
            "paper_ready": readiness.get("paper_ready"),
            "verdict": readiness.get("verdict"),
            "section_status": readiness.get("section_status"),
        },
        "artifacts": artifacts,
        "writable_sections": [s.get("section") for s in writable],
        "blocked_sections": [
            {"section": s.get("section"), "percent": s.get("readiness_percent")}
            for s in blocked
        ],
        "instruction": (
            f"Write paper draft in {'Korean' if language.startswith('ko') else 'English'}. "
            "Read artifacts listed above from repo root. "
            "Follow paper-intake-curate and paper-section-mapping skills. "
            "writable sections → full prose with citations; others → gap bullets only."
        ),
        "readiness_summary": format_readiness_summary(readiness),
    }


def write_paper_draft_prompt(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = project_dir / "intake" / "paper_draft_prompt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def draft_output_path(project_dir: Path) -> Path:
    return project_dir / "knowledge" / "obsidian" / "06-paper" / "DRAFT.md"


def run_paper_draft_llm(root: Path, project_id: str, campaign: str, *, language: str = "ko") -> dict[str, Any]:
    """Invoke LLM to write DRAFT.md (openai_compatible only)."""
    from soc_verify.config import load_user_config
    from soc_verify.llm_runner import (
        _assistant_content_from_openai_response,
        _read_template,
        openai_chat_completions,
    )
    from soc_verify.setup_llm import load_secrets_into_environ

    root = root.resolve()
    project_dir = root / "projects" / project_id
    payload = build_paper_draft_prompt(root, project_id, campaign, language=language)
    write_paper_draft_prompt(project_dir, payload)

    try:
        config = load_user_config(root)
    except FileNotFoundError:
        return {"ok": False, "error": "config.json missing"}

    lc = config.raw.get("llm") or {}
    mode = str(lc.get("mode", "stub"))
    result: dict[str, Any] = {"ok": False, "mode": mode, "invoked": False}

    if mode != "openai_compatible":
        result["error"] = "llm.mode must be openai_compatible — use prompt file with external LLM"
        result["prompt"] = str(project_dir / "intake" / "paper_draft_prompt.json")
        return result

    load_secrets_into_environ(root)
    user_msg = json.dumps(payload, indent=2, ensure_ascii=False)
    system = _read_template("system_paper_draft.txt")
    try:
        resp = openai_chat_completions(
            lc,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            task="graph_driver",
        )
        content = _assistant_content_from_openai_response(resp).strip()
        if content.startswith("```"):
            import re

            m = re.match(r"^```(?:markdown|md)?\s*\n(.*)```\s*$", content, re.DOTALL | re.IGNORECASE)
            if m:
                content = m.group(1).strip()
        out = draft_output_path(project_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content + "\n", encoding="utf-8")
        result.update({"ok": True, "invoked": True, "draft": str(out.relative_to(project_dir)), "chars": len(content)})
    except Exception as exc:
        result["error"] = str(exc)
    return result