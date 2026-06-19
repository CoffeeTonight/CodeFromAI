"""Knowledge intake — collect Confluence/wiki/doc/md → LLM → uniform Obsidian MD."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from glob import glob as glob_paths
from pathlib import Path
from typing import Any
from urllib import error, request

from soc_verify.config import UserConfig, load_user_config
from soc_verify.llm_runner import (
    _assistant_content_from_openai_response,
    _read_template,
    openai_chat_completions,
)
from soc_verify.models import load_yaml, save_yaml
from soc_verify.obsidian_md import (
    build_intake_ast,
    intake_relpaths,
    intake_source_slug,
    render_intake_source_note,
    render_sources_moc,
)
from soc_verify.paper_intake_skills import (
    bootstrap_paper_intake_skills,
    paper_skills_prompt_block,
)
from soc_verify.setup_llm import load_secrets_into_environ


SPEC_NAME = "knowledge_intake_spec.yaml"
SOURCES_NAME = "knowledge_sources.yaml"


def load_spec(root: Path) -> dict[str, Any]:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return load_yaml(p) or {}


def sources_path(project_dir: Path) -> Path:
    return project_dir / "intake" / SOURCES_NAME


def load_sources(project_dir: Path) -> dict[str, Any]:
    path = sources_path(project_dir)
    if not path.is_file():
        return {"contract": "knowledge_sources_v1", "project_id": project_dir.name, "sources": []}
    data = load_yaml(path)
    if not isinstance(data, dict):
        return {"contract": "knowledge_sources_v1", "project_id": project_dir.name, "sources": []}
    data.setdefault("sources", [])
    return data


def save_sources(project_dir: Path, data: dict[str, Any]) -> Path:
    path = sources_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_yaml(path, data)
    return path


def _limits(spec: dict[str, Any]) -> dict[str, int]:
    lim = spec.get("limits") or {}
    return {
        "per_source": int(lim.get("max_chars_per_source", 32000)),
        "total": int(lim.get("max_total_chars", 120000)),
        "max_files": int(lim.get("max_files_per_dir", 40)),
    }


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 40] + "\n\n… [truncated]\n"


def _read_text_file(path: Path, max_chars: int) -> str:
    if not path.is_file():
        return ""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return _truncate(raw, max_chars)


def _fetch_url(url: str, max_chars: int, timeout: int = 30) -> str:
    try:
        req = request.Request(url, headers={"User-Agent": "soc-verify-agent/0.1"})
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        return _truncate(body, max_chars)
    except (error.URLError, TimeoutError, ValueError) as exc:
        return f"[fetch failed: {exc}]"


def _collect_markdown_dir(path: Path, max_chars: int, max_files: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    if not path.is_dir():
        return chunks
    files = sorted(path.rglob("*.md"))[:max_files]
    for f in files:
        chunks.append(
            {
                "path": str(f),
                "content": _read_text_file(f, max_chars // max(1, len(files))),
            }
        )
    return chunks


def _resolve_path(root: Path, raw: str, project_dir: Path | None = None) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    if project_dir is not None:
        cand = (project_dir / raw).resolve()
        if cand.is_file() or cand.is_dir():
            return cand
    return (root / raw).resolve()


def collect_source(
    root: Path,
    source: dict[str, Any],
    *,
    spec: dict[str, Any] | None = None,
    project_dir: Path | None = None,
) -> dict[str, Any]:
    """Collect text from one source definition."""
    spec = spec or load_spec(root)
    lim = _limits(spec)
    stype = str(source.get("type", ""))
    out: dict[str, Any] = {"type": stype, "label": source.get("label", stype), "ok": False, "content": ""}

    if stype == "discovered":
        return out

    if stype == "confluence":
        parts: list[str] = []
        if source.get("page_id"):
            parts.append(f"confluence_page_id: {source['page_id']}")
        if source.get("url"):
            parts.append(f"url: {source['url']}")
            parts.append(_fetch_url(str(source["url"]), lim["per_source"]))
        export_path = source.get("export_path")
        if export_path:
            p = _resolve_path(root, str(export_path), project_dir)
            parts.append(_read_text_file(p, lim["per_source"]))
        out["content"] = _truncate("\n\n".join(p for p in parts if p), lim["per_source"])
        out["ok"] = bool(out["content"])
        return out

    if stype in ("wiki", "url"):
        url = str(source.get("url", ""))
        out["content"] = _fetch_url(url, lim["per_source"]) if url else ""
        out["ok"] = bool(out["content"]) and not out["content"].startswith("[fetch failed")
        return out

    if stype == "markdown":
        p = _resolve_path(root, str(source.get("path", "")), project_dir)
        out["content"] = _read_text_file(p, lim["per_source"])
        out["ok"] = bool(out["content"])
        out["path"] = str(p)
        return out

    if stype == "markdown_dir":
        p = _resolve_path(root, str(source.get("path", "")), project_dir)
        chunks = _collect_markdown_dir(p, lim["per_source"], lim["max_files"])
        out["files"] = [c["path"] for c in chunks]
        out["content"] = _truncate(
            "\n\n---\n\n".join(f"# {c['path']}\n{c['content']}" for c in chunks),
            lim["per_source"],
        )
        out["ok"] = bool(chunks)
        return out

    if stype == "doc":
        p = _resolve_path(root, str(source.get("path", "")), project_dir)
        out["content"] = _read_text_file(p, lim["per_source"])
        out["ok"] = bool(out["content"])
        return out

    out["content"] = f"[unknown source type: {stype}]"
    return out


def _discovered_source(project_dir: Path) -> dict[str, Any]:
    disc = load_yaml(project_dir / "discovered.yaml") or {}
    state = load_yaml(project_dir / "state.yaml") or {}
    return {
        "type": "discovered",
        "label": "discovered.yaml + state.yaml",
        "ok": True,
        "content": json.dumps(
            {"discovered": disc, "state": {k: state.get(k) for k in (
                "schedule_plan", "current_milestone", "milestones", "verification_groups_due"
            )}},
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
    }


def list_verification_gates(project_dir: Path) -> list[dict[str, str]]:
    gates: list[dict[str, str]] = []
    ver = project_dir / "verification"
    if not ver.is_dir():
        return gates
    for stage_dir in sorted(ver.iterdir()):
        if not stage_dir.is_dir():
            continue
        for group_dir in sorted(stage_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            manifest = group_dir / "manifest.yaml"
            if manifest.is_file():
                m = load_yaml(manifest) or {}
                gates.append(
                    {
                        "stage": stage_dir.name,
                        "group": group_dir.name,
                        "milestone": str(m.get("milestone", "")),
                        "spec": str(group_dir.relative_to(project_dir.parent.parent)),
                    }
                )
    return gates


def collect_knowledge_bundle(root: Path, project_id: str) -> dict[str, Any]:
    root = root.resolve()
    project_dir = root / "projects" / project_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"project not found: {project_id}")

    bootstrap_paper_intake_skills(project_dir, root)

    spec = load_spec(root)
    lim = _limits(spec)
    src_cfg = load_sources(project_dir)
    sources = list(src_cfg.get("sources") or [])

    collected: list[dict[str, Any]] = [_discovered_source(project_dir)]
    total = len(collected[0].get("content", ""))

    for src in sources:
        if not isinstance(src, dict):
            continue
        item = collect_source(root, src, spec=spec, project_dir=project_dir)
        collected.append(item)
        total += len(item.get("content", ""))
        if total >= lim["total"]:
            break

    bundle = {
        "contract": "knowledge_bundle_v1",
        "project_id": project_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "sources": collected,
        "gates": list_verification_gates(project_dir),
    }
    out_dir = project_dir / "intake"
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = out_dir / "knowledge_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    write_intake_obsidian_layer(project_dir, bundle)
    _sync_paper_progress_safe(root, project_id)
    return bundle


def _sync_paper_progress_safe(root: Path, project_id: str) -> None:
    try:
        from soc_verify.paper_progress import load_spec, resolve_paper_project, sync_paper_progress

        spec = load_spec(root)
        campaign = str(spec.get("default_campaign", "paper_eval_2026"))
        pid = resolve_paper_project(root, campaign, project_id)
        if pid:
            sync_paper_progress(root, pid, campaign, write_llm_prompt=True)
    except (FileNotFoundError, OSError, ValueError):
        pass


def write_intake_obsidian_layer(
    project_dir: Path,
    bundle: dict[str, Any],
    *,
    normalize_result: dict[str, Any] | None = None,
) -> list[str]:
    """Obsidian AST layer for collected sources (05-intake) — mirrors runtime intake/."""
    pid = project_dir.name
    base = project_dir / "knowledge" / "obsidian" / "05-intake"
    sources_dir = base / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    pairs: list[tuple[str, dict[str, Any]]] = []
    for i, src in enumerate(bundle.get("sources") or []):
        if not isinstance(src, dict):
            continue
        slug = intake_source_slug(i, src)
        pairs.append((slug, src))
        note_path = sources_dir / f"{slug}.md"
        note_path.write_text(render_intake_source_note(pid, slug, src, index=i), encoding="utf-8")

    rel = intake_relpaths()
    moc_path = base / "SOURCES-MOC.md"
    skill_ids: list[str] = []
    manifest_path = project_dir / "intake" / "paper_intake_skills.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        skill_ids = list(manifest.get("skill_ids") or [])
    moc_path.write_text(
        render_sources_moc(
            pid,
            pairs,
            collected_at=str(bundle.get("collected_at", "")),
            normalize_ok=normalize_result.get("ok") if normalize_result else None,
            paper_skill_ids=skill_ids or None,
        ),
        encoding="utf-8",
    )
    intake_json = base / "intake.json"
    ast_payload = build_intake_ast(pid, bundle, sources=pairs, normalize_result=normalize_result)
    if manifest_path.is_file():
        ast_payload["paper_intake_skills"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    intake_json.write_text(
        json.dumps(ast_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return [
        str(moc_path.relative_to(project_dir)),
        str(intake_json.relative_to(project_dir)),
        *[str((sources_dir / f"{slug}.md").relative_to(project_dir)) for slug, _ in pairs],
    ]


def _project_template_path(root: Path) -> Path:
    return root / "templates" / "obsidian" / "projects" / "_PROJECT_TEMPLATE.md"


def _build_user_prompt(bundle: dict[str, Any], root: Path) -> str:
    template = ""
    tpl = _project_template_path(root)
    if tpl.is_file():
        template = tpl.read_text(encoding="utf-8")
    project_id = str(bundle.get("project_id", ""))
    project_dir = root / "projects" / project_id
    paper_block: dict[str, Any] = {}
    if project_dir.is_dir():
        paper_block = paper_skills_prompt_block(project_dir, root)

    return json.dumps(
        {
            "task": "normalize_to_obsidian_project_note",
            "project_id": bundle.get("project_id"),
            "output_template": template,
            "project_context": {
                "gates": bundle.get("gates"),
            },
            "sources": bundle.get("sources"),
            "paper_intake_skills": paper_block,
            "instructions": (
                "Merge sources into one Obsidian note matching output_template structure. "
                "Fill Overview from Confluence/wiki/md content. "
                "Build verification gates table from project_context.gates when present. "
                "Follow paper_intake_skills.primary_skill_excerpt — publication-grade: "
                "cite every fact, tag evidence_type, list paper gaps, map to paper sections."
            ),
        },
        indent=2,
        ensure_ascii=False,
    )


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)```\s*$", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else text


def normalize_to_obsidian(
    root: Path,
    project_id: str,
    *,
    config: UserConfig | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """LLM: knowledge bundle → uniform Obsidian MD."""
    root = root.resolve()
    project_dir = root / "projects" / project_id
    bundle_path = project_dir / "intake" / "knowledge_bundle.json"
    if not bundle_path.is_file() or force:
        bundle = collect_knowledge_bundle(root, project_id)
    else:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    out_repo = root / "templates" / "obsidian" / "projects" / f"{project_id}.md"
    prompt_path = project_dir / "intake" / "knowledge_normalize_prompt.json"
    user_msg = _build_user_prompt(bundle, root)
    prompt_path.write_text(user_msg, encoding="utf-8")

    if config is None:
        try:
            config = load_user_config(root)
        except FileNotFoundError:
            config = UserConfig(raw={"llm": {"mode": "stub"}}, path=root / "config.json")

    lc = config.raw.get("llm") or {}
    mode = str(lc.get("mode", "stub"))
    system = _read_template("system_knowledge_normalize.txt")

    result: dict[str, Any] = {
        "project_id": project_id,
        "mode": mode,
        "repo_note": str(out_repo),
        "invoked": False,
    }

    if mode == "openai_compatible":
        load_secrets_into_environ(root)
        try:
            resp = openai_chat_completions(
                lc,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                task="graph_driver",
            )
            content = _strip_markdown_fence(_assistant_content_from_openai_response(resp))
            out_repo.parent.mkdir(parents=True, exist_ok=True)
            out_repo.write_text(content, encoding="utf-8")
            result["invoked"] = True
            result["ok"] = True
            result["chars"] = len(content)
        except Exception as exc:
            result["ok"] = False
            result["error"] = str(exc)
    else:
        stub = _fallback_stub_note(bundle, root)
        out_repo.parent.mkdir(parents=True, exist_ok=True)
        out_repo.write_text(stub, encoding="utf-8")
        result["ok"] = True
        result["stub"] = True
        result["message"] = "llm.mode!=openai_compatible — wrote template stub; fill via LLM or re-run after setup llm"

    vault_rel = (config.raw.get("paths") or {}).get("obsidian_vault")
    if vault_rel and result.get("ok"):
        vault = _resolve_path(root, str(vault_rel))
        spec = load_spec(root)
        sub = str((spec.get("output") or {}).get("vault_subpath", "05-Agents/projects/{project_id}.md"))
        vault_out = vault / sub.format(project_id=project_id)
        vault_out.parent.mkdir(parents=True, exist_ok=True)
        vault_out.write_text(out_repo.read_text(encoding="utf-8"), encoding="utf-8")
        result["vault_note"] = str(vault_out)

    meta_path = project_dir / "intake" / "knowledge_normalize_result.json"
    meta_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_intake_obsidian_layer(project_dir, bundle, normalize_result=result)
    return result


def _fallback_stub_note(bundle: dict[str, Any], root: Path) -> str:
    pid = str(bundle.get("project_id", "PROJECT"))
    disc = {}
    for s in bundle.get("sources") or []:
        if s.get("type") == "discovered":
            try:
                disc = json.loads(s.get("content", "{}")).get("discovered", {})
            except json.JSONDecodeError:
                pass
    milestone = disc.get("current_milestone") or "M?"
    tpl = _project_template_path(root)
    text = tpl.read_text(encoding="utf-8") if tpl.is_file() else f"# Project — {pid}\n"
    gates = bundle.get("gates") or []
    if gates:
        rows = ["| stage | group | milestone | spec |", "|-------|-------|-----------|------|"]
        for g in gates:
            rows.append(f"| {g.get('stage')} | {g.get('group')} | {g.get('milestone')} | `{g.get('spec')}` |")
        gates_table = "\n".join(rows)
    else:
        gates_table = "(no gates discovered)"
    sources_lines = []
    for s in bundle.get("sources") or []:
        sources_lines.append(f"- **{s.get('label', s.get('type'))}**: {s.get('type')}")
    return (
        text.replace("{{PROJECT_ID}}", pid)
        .replace("{{MILESTONE}}", str(milestone))
        .replace("{{SCHEDULE_PLAN}}", str(disc.get("schedule_plan", "")))
        .replace("{{GIT_URL}}", str(disc.get("git_url", "")))
        .replace("{{DOC_REV}}", str(disc.get("doc_rev", "")))
        .replace("{{OVERVIEW}}", "_LLM normalize pending — run after `soc-verify setup llm`._")
        .replace("{{GATES_TABLE}}", gates_table)
        .replace("{{SOURCES_LIST}}", "\n".join(sources_lines))
        .replace("MISSION_{{PROJECT_ID}}", f"MISSION_{pid}")
    )


def add_source_interactive(
    project_dir: Path,
    *,
    source_type: str,
    location: str,
    label: str = "",
    root: Path | None = None,
) -> dict[str, Any]:
    """Append one source to knowledge_sources.yaml."""
    data = load_sources(project_dir)
    entry: dict[str, Any] = {"type": source_type, "label": label or source_type}
    if source_type in ("confluence", "wiki", "url"):
        if location.startswith("http"):
            entry["url"] = location
        elif source_type == "confluence" and location.isdigit():
            entry["page_id"] = location
        else:
            entry["export_path"] = location
    else:
        entry["path"] = location
    data["sources"].append(entry)
    save_sources(project_dir, data)
    return entry


def seed_sources_from_discovered(project_dir: Path) -> dict[str, Any]:
    """Auto-add discovered.yaml hints as sources."""
    disc = load_yaml(project_dir / "discovered.yaml") or {}
    data = load_sources(project_dir)
    existing = {json.dumps(s, sort_keys=True) for s in data.get("sources") or [] if isinstance(s, dict)}

    def _add(entry: dict[str, Any]) -> None:
        key = json.dumps(entry, sort_keys=True)
        if key not in existing:
            data["sources"].append(entry)
            existing.add(key)

    if disc.get("doc_path"):
        p = Path(str(disc["doc_path"]))
        if p.suffix == ".md" or "/" in str(disc["doc_path"]):
            _add({"type": "markdown", "path": str(disc["doc_path"]), "label": "doc_path from discovered"})
    if disc.get("confluence_page_id"):
        _add(
            {
                "type": "confluence",
                "page_id": str(disc["confluence_page_id"]),
                "label": "Confluence (discovered)",
            }
        )
    save_sources(project_dir, data)
    return data