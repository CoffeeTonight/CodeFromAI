"""Obsidian-compatible Markdown builders — AST vault layout, tags, wikilinks, frontmatter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# Numbered layers — folder path encodes AST node kind (see registry/obsidian_ast_spec.yaml)
LAYER_INDEX = "00-index"
LAYER_MILESTONES = "01-milestones"
LAYER_STAGES = "02-stages"
LAYER_NODES = "03-nodes"
LAYER_SKILLS = "04-skills"
LAYER_INTAKE = "05-intake"
LAYER_PAPER = "06-paper"

INTAKE_EXCERPT_CHARS = 4000


def wikilink(*parts: str) -> str:
    """Build Obsidian wikilink from vault-relative path segments."""
    path = "/".join(p.strip("/") for p in parts if p)
    return f"[[{path}]]"


def obsidian_frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def _vault_base(project_id: str) -> str:
    return f"projects/{project_id}/knowledge/obsidian"


def obsidian_relpaths(entry: dict[str, Any]) -> dict[str, str]:
    """Vault-relative paths (under knowledge/obsidian/) — mirrors AST folder hierarchy."""
    nid = str(entry.get("id", ""))
    stage = str(entry.get("stage", ""))
    group = str(entry.get("group", ""))
    milestone = str(entry.get("milestone", ""))
    gate_dir = f"{LAYER_STAGES}/{stage}/groups/{group}"
    return {
        "index_moc": f"{LAYER_INDEX}/PROJECT-MOC.md",
        "graph_json": f"{LAYER_INDEX}/graph.json",
        "milestone_moc": f"{LAYER_MILESTONES}/{milestone}/MOC.md",
        "milestone_json": f"{LAYER_MILESTONES}/{milestone}/milestone.json",
        "node_hub": f"{LAYER_NODES}/{nid}.md",
        "index_json": f"{LAYER_NODES}/{nid}.json",
        "skill": f"{LAYER_SKILLS}/{nid}.md",
        "check": f"{gate_dir}/CHECK.md",
        "respond": f"{gate_dir}/RESPOND.md",
        "milestone": f"{gate_dir}/MILESTONE.md",
        "gate_json": f"{gate_dir}/gate.json",
    }


def intake_relpaths() -> dict[str, str]:
    return {
        "sources_moc": f"{LAYER_INTAKE}/SOURCES-MOC.md",
        "intake_json": f"{LAYER_INTAKE}/intake.json",
    }


def intake_source_slug(index: int, source: dict[str, Any]) -> str:
    stype = str(source.get("type", "unknown"))
    label = str(source.get("label", stype)).lower()
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label).strip("-")
    safe = safe[:40] or stype
    return f"{stype}-{index}-{safe}"


def intake_source_relpath(slug: str) -> str:
    return f"{LAYER_INTAKE}/sources/{slug}.md"


def obsidian_paths(project_id: str, entry: dict[str, Any]) -> dict[str, str]:
    """Repo-relative paths including project prefix."""
    base = _vault_base(project_id)
    rel = obsidian_relpaths(entry)
    return {k: f"{base}/{v}" for k, v in rel.items()}


def _header_block(
    title: str,
    *,
    tags: list[str],
    uplinks: list[str],
    project_id: str,
) -> str:
    tag_line = " ".join(f"`#{t}`" for t in tags)
    links = " · ".join(uplinks)
    return f"""# {title}

태그: {tag_line}
프로젝트: {wikilink("projects", project_id)} · {links}

---
"""


def _gate_wikilinks(stage: str, group: str) -> dict[str, str]:
    base = f"{LAYER_STAGES}/{stage}/groups/{group}"
    return {
        "check": wikilink(base, "CHECK"),
        "respond": wikilink(base, "RESPOND"),
        "milestone": wikilink(base, "MILESTONE"),
    }


def render_node_hub_note(project_id: str, entry: dict[str, Any]) -> str:
    nid = str(entry.get("id", ""))
    stage = str(entry.get("stage", ""))
    group = str(entry.get("group", ""))
    milestone = str(entry.get("milestone", ""))
    gates = _gate_wikilinks(stage, group)
    fm = obsidian_frontmatter(
        {
            "type": "node_hub",
            "ast_layer": LAYER_NODES,
            "project_id": project_id,
            "node_id": nid,
            "stage": stage,
            "group": group,
            "milestone": milestone,
            "tags": [f"project/{project_id}", f"node/{nid}", f"stage/{stage}", f"milestone/{milestone}"],
        }
    )
    requires = entry.get("requires") or []
    req_links = ", ".join(f"`{r}`" for r in requires) or "(none)"
    body = f"""{_header_block(
        f"Node — {entry.get('label_ko') or group}",
        tags=[f"project/{project_id}", f"node/{nid}"],
        uplinks=[
            wikilink(LAYER_INDEX, "PROJECT-MOC"),
            wikilink(LAYER_MILESTONES, milestone, "MOC"),
            wikilink("00-HUB"),
            wikilink("01-GRAPH-FLOW"),
        ],
        project_id=project_id,
    )}

## Overview

{entry.get('what_to_do', '').strip()}

## Graph

| 필드 | 값 |
|------|-----|
| node_id | `{nid}` |
| stage / group | `{stage}` / `{group}` |
| milestone | `{milestone}` |
| requires | {req_links} |
| graph | `{entry.get('graph', 'verify_group')}` |

## Linked gate notes

- {gates['check']}
- {gates['respond']}
- {gates['milestone']}
- {wikilink(LAYER_SKILLS, nid)}

## AST sidecar

- `{LAYER_NODES}/{nid}.json`
- `{LAYER_STAGES}/{stage}/groups/{group}/gate.json`

## Agent

```bash
soc-verify --root . graph start --graph verify_group --project {project_id} --stage {stage} --group {group}
```
"""
    return fm + "\n\n" + body


def render_skill_note(project_id: str, entry: dict[str, Any]) -> str:
    nid = str(entry.get("id", ""))
    body_text = str(entry.get("skill_body") or entry.get("what_to_do", "")).strip()
    fm = obsidian_frontmatter(
        {
            "type": "skill",
            "ast_layer": LAYER_SKILLS,
            "project_id": project_id,
            "node_id": nid,
            "tags": [f"project/{project_id}", f"skill/{nid}"],
        }
    )
    header = _header_block(
        f"Skill — {entry.get('label_ko') or nid}",
        tags=[f"skill/{nid}", f"project/{project_id}"],
        uplinks=[
            wikilink(LAYER_INDEX, "PROJECT-MOC"),
            wikilink(LAYER_NODES, nid),
        ],
        project_id=project_id,
    )
    return fm + "\n\n" + header + "\n" + body_text + "\n"


def render_check_note(project_id: str, entry: dict[str, Any]) -> str:
    stage = str(entry.get("stage", ""))
    group = str(entry.get("group", ""))
    nid = str(entry.get("id", ""))
    milestone = str(entry.get("milestone", ""))
    gates = _gate_wikilinks(stage, group)
    hints = str(entry.get("check_hints", "")).strip() or str(entry.get("what_to_do", "")).strip()
    fm = obsidian_frontmatter(
        {
            "type": "gate_check",
            "ast_layer": LAYER_STAGES,
            "project_id": project_id,
            "stage": stage,
            "group": group,
            "node_id": nid,
            "tags": [f"gate/{stage}/{group}", f"project/{project_id}", "check"],
        }
    )
    header = _header_block(
        f"CHECK — {group} ({stage})",
        tags=[f"gate/{stage}/{group}", "check"],
        uplinks=[
            wikilink(LAYER_INDEX, "PROJECT-MOC"),
            wikilink(LAYER_MILESTONES, milestone, "MOC"),
            wikilink("00-HUB"),
            wikilink("01-GRAPH-FLOW"),
            wikilink(LAYER_NODES, nid),
        ],
        project_id=project_id,
    )
    return fm + "\n\n" + header + f"""
## 이 노드에서 할 일

{entry.get('what_to_do', '').strip()}

## PASS 조건

- `verdict_{group}.json`: `status == PASS`
{hints}

## FAIL 시 확인

- `runs/{{run_id}}/{group}.log`
- {gates['milestone']} milestone·depends 일치
- manifest: `projects/{project_id}/verification/{stage}/{group}/manifest.yaml`
"""


def render_respond_note(project_id: str, entry: dict[str, Any]) -> str:
    stage = str(entry.get("stage", ""))
    group = str(entry.get("group", ""))
    nid = str(entry.get("id", ""))
    gates = _gate_wikilinks(stage, group)
    fm = obsidian_frontmatter(
        {
            "type": "gate_respond",
            "ast_layer": LAYER_STAGES,
            "project_id": project_id,
            "stage": stage,
            "group": group,
            "node_id": nid,
        }
    )
    header = _header_block(
        f"RESPOND — {group}",
        tags=[f"gate/{stage}/{group}", "respond"],
        uplinks=[gates["check"]],
        project_id=project_id,
    )
    return fm + "\n\n" + header + f"""
- {gates['check']} 기준으로 verdict 작성
- milestone: **{entry.get('milestone', '')}**
- node: {wikilink(LAYER_NODES, nid)}
"""


def render_milestone_note(project_id: str, entry: dict[str, Any]) -> str:
    stage = str(entry.get("stage", ""))
    group = str(entry.get("group", ""))
    nid = str(entry.get("id", ""))
    milestone = str(entry.get("milestone", ""))
    fm = obsidian_frontmatter(
        {
            "type": "gate_milestone",
            "ast_layer": LAYER_STAGES,
            "project_id": project_id,
            "milestone": milestone,
            "node_id": nid,
        }
    )
    header = _header_block(
        f"MILESTONE — {group}",
        tags=[f"milestone/{milestone}", f"gate/{stage}/{group}"],
        uplinks=[
            wikilink(LAYER_NODES, nid),
            wikilink(LAYER_MILESTONES, milestone, "MOC"),
        ],
        project_id=project_id,
    )
    return fm + "\n\n" + header + f"""
| 항목 | 값 |
|------|-----|
| target_milestone | **{milestone}** |
| node_guide_id | `{nid}` |
| stage / group | `{stage}` / `{group}` |

선행: {', '.join(f'`{r}`' for r in (entry.get('requires') or [])) or '(none)'}
"""


def _excerpt(text: str, max_chars: int = INTAKE_EXCERPT_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 40] + "\n\n… [truncated — see intake/knowledge_bundle.json]\n"


def render_intake_source_note(
    project_id: str,
    slug: str,
    source: dict[str, Any],
    *,
    index: int,
) -> str:
    stype = str(source.get("type", ""))
    label = str(source.get("label", stype))
    fm = obsidian_frontmatter(
        {
            "type": "intake_source",
            "ast_layer": LAYER_INTAKE,
            "project_id": project_id,
            "source_id": slug,
            "source_type": stype,
            "source_index": index,
            "ok": bool(source.get("ok")),
            "tags": [f"project/{project_id}", "intake", f"source/{stype}"],
        }
    )
    path_hint = source.get("path") or source.get("url") or ""
    body = f"""# Source — {label}

상위: {wikilink(LAYER_INTAKE, 'SOURCES-MOC')} · {wikilink(LAYER_INDEX, 'PROJECT-MOC')}
타입: `{stype}` · slug: `{slug}`
런타임: `intake/knowledge_bundle.json` (전체 본문)

---

## Provenance

| 필드 | 값 |
|------|-----|
| type | `{stype}` |
| label | {label} |
| path/url | `{path_hint or '(bundle)'}` |
| ok | `{source.get('ok')}` |

## Excerpt

{_excerpt(str(source.get('content', '')))}
"""
    return fm + "\n\n" + body


def render_sources_moc(
    project_id: str,
    sources: list[tuple[str, dict[str, Any]]],
    *,
    collected_at: str = "",
    normalize_ok: bool | None = None,
    paper_skill_ids: list[str] | None = None,
) -> str:
    fm = obsidian_frontmatter(
        {
            "type": "intake_moc",
            "ast_layer": LAYER_INTAKE,
            "project_id": project_id,
            "tags": [f"project/{project_id}", "intake", "moc"],
        }
    )
    lines = []
    for slug, src in sources:
        stype = str(src.get("type", ""))
        label = str(src.get("label", stype))
        ok = "✓" if src.get("ok") else "✗"
        lines.append(f"- {ok} {wikilink(LAYER_INTAKE, 'sources', slug)} — `{stype}` {label}")

    norm_line = ""
    if normalize_ok is not None:
        norm_line = f"\n정규화: `{'PASS' if normalize_ok else 'PENDING'}` → `templates/obsidian/projects/{project_id}.md`\n"

    body = f"""# Sources MOC — {project_id}

상위: {wikilink(LAYER_INDEX, 'PROJECT-MOC')} · AST: `{LAYER_INTAKE}/intake.json`
런타임 파이프라인: `intake/knowledge_sources.yaml` · `intake/knowledge_bundle.json`
수집: `{collected_at or '(unknown)'}`{norm_line}

---

## Collected sources

{chr(10).join(lines) or '(none)'}

## Paper intake skills (논문급 정리 SSOT)

{chr(10).join(f'- {wikilink(LAYER_SKILLS, sid)}' for sid in (paper_skill_ids or ['paper-intake-hub', 'paper-intake-curate']))}

주 작업: {wikilink(LAYER_SKILLS, 'paper-intake-curate')} · 허브: {wikilink(LAYER_SKILLS, 'paper-intake-hub')}

## Layer role

| 구분 | 경로 | 용도 |
|------|------|------|
| Obsidian (읽기·링크) | `{LAYER_INTAKE}/` | AST 파서·wikilink |
| Runtime (JSON/YAML) | `intake/` | bundle·prompt·결과 |
"""
    return fm + "\n\n" + body


def build_intake_ast(
    project_id: str,
    bundle: dict[str, Any],
    *,
    sources: list[tuple[str, dict[str, Any]]] | None = None,
    normalize_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rel = intake_relpaths()
    if sources is None:
        sources = [
            (intake_source_slug(i, s), s)
            for i, s in enumerate(bundle.get("sources") or [])
            if isinstance(s, dict)
        ]
    return {
        "contract": "obsidian_intake_v1",
        "project_id": project_id,
        "ast_layer": LAYER_INTAKE,
        "moc": rel["sources_moc"],
        "sidecar": rel["intake_json"],
        "runtime_dir": "intake",
        "runtime_artifacts": {
            "sources": "intake/knowledge_sources.yaml",
            "bundle": "intake/knowledge_bundle.json",
            "normalize_prompt": "intake/knowledge_normalize_prompt.json",
            "normalize_result": "intake/knowledge_normalize_result.json",
        },
        "collected_at": bundle.get("collected_at"),
        "source_count": len(sources),
        "sources": [
            {
                "id": slug,
                "note": intake_source_relpath(slug),
                "type": str(src.get("type", "")),
                "label": str(src.get("label", "")),
                "ok": bool(src.get("ok")),
            }
            for slug, src in sources
        ],
        "normalize": normalize_result or {},
        "edges": [
            {"from": intake_source_relpath(slug), "to": rel["sources_moc"], "type": "indexed_by"}
            for slug, _ in sources
        ],
    }


def render_project_moc(project_id: str, entries: list[dict[str, Any]]) -> str:
    fm = obsidian_frontmatter(
        {
            "type": "project_moc",
            "ast_layer": LAYER_INDEX,
            "project_id": project_id,
            "tags": [f"project/{project_id}", "moc", "ast-root"],
        }
    )
    milestones: dict[str, list[str]] = {}
    for e in entries:
        m = str(e.get("milestone", ""))
        milestones.setdefault(m, []).append(str(e.get("id", "")))

    ms_lines = []
    for m in sorted(milestones):
        nodes = ", ".join(wikilink(LAYER_NODES, n) for n in sorted(milestones[m]))
        ms_lines.append(f"- **{m}**: {wikilink(LAYER_MILESTONES, m, 'MOC')} — {nodes}")

    node_lines = []
    for e in sorted(entries, key=lambda x: str(x.get("id", ""))):
        nid = str(e.get("id", ""))
        stage = str(e.get("stage", ""))
        group = str(e.get("group", ""))
        gates = _gate_wikilinks(stage, group)
        node_lines.append(
            f"- {wikilink(LAYER_NODES, nid)} → {gates['check']} · {wikilink(LAYER_SKILLS, nid)}"
        )

    body = f"""# Project MOC — {project_id}

태그: `#project/{project_id}` `#moc` `#ast-root`
AST: `{LAYER_INDEX}/graph.json` · 플랫폼: {wikilink('00-HUB')} · {wikilink('01-GRAPH-FLOW')}

---

## Intake (수집)

- {wikilink(LAYER_INTAKE, 'SOURCES-MOC')} · 런타임: `intake/knowledge_bundle.json`

## Paper progress (논문 퍼즐 %%)

- {wikilink(LAYER_PAPER, 'PROGRESS')} · `intake/paper_progress_judgment.json`

## Milestones

{chr(10).join(ms_lines) or '(none)'}

## Nodes

{chr(10).join(node_lines) or '(none)'}

## Vault layers

| Layer | Role |
|-------|------|
| `{LAYER_INDEX}/` | MOC + graph.json (AST SSOT) |
| `{LAYER_MILESTONES}/` | 마일스톤별 MOC |
| `{LAYER_STAGES}/` | stage → group → CHECK/RESPOND/MILESTONE |
| `{LAYER_NODES}/` | 노드 허브 + JSON sidecar |
| `{LAYER_SKILLS}/` | SKILL 본문 |
| `{LAYER_INTAKE}/` | 수집 소스 MOC + excerpt (런타임 `intake/` 미러) |
| `{LAYER_PAPER}/` | 논문 완성 퍼즐 다이어그램 + %% |
"""
    return fm + "\n\n" + body


def render_milestone_moc(project_id: str, milestone: str, entries: list[dict[str, Any]]) -> str:
    scoped = [e for e in entries if str(e.get("milestone", "")) == milestone]
    fm = obsidian_frontmatter(
        {
            "type": "milestone_moc",
            "ast_layer": LAYER_MILESTONES,
            "project_id": project_id,
            "milestone": milestone,
            "tags": [f"project/{project_id}", f"milestone/{milestone}", "moc"],
        }
    )
    lines = []
    for e in sorted(scoped, key=lambda x: str(x.get("id", ""))):
        nid = str(e.get("id", ""))
        stage = str(e.get("stage", ""))
        group = str(e.get("group", ""))
        gates = _gate_wikilinks(stage, group)
        lines.append(f"- {wikilink(LAYER_NODES, nid)}: {gates['check']}")

    body = f"""# Milestone — {milestone}

상위: {wikilink(LAYER_INDEX, 'PROJECT-MOC')} · AST: `{LAYER_INDEX}/graph.json`

---

## Nodes in {milestone}

{chr(10).join(lines) or '(none)'}
"""
    return fm + "\n\n" + body


def gate_json_sidecar(project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    rel = obsidian_relpaths(entry)
    stage = str(entry.get("stage", ""))
    group = str(entry.get("group", ""))
    return {
        "contract": "obsidian_gate_v1",
        "project_id": project_id,
        "stage": stage,
        "group": group,
        "node_id": str(entry.get("id", "")),
        "milestone": str(entry.get("milestone", "")),
        "requires": list(entry.get("requires") or []),
        "notes": {
            "check": rel["check"],
            "respond": rel["respond"],
            "milestone": rel["milestone"],
        },
        "node_hub": rel["node_hub"],
        "skill": rel["skill"],
    }


def build_graph_ast(
    project_id: str,
    entries: list[dict[str, Any]],
    *,
    intake: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full vault AST — SSOT for parsers and graph tooling."""
    nodes: dict[str, Any] = {}
    milestones: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        nid = str(entry.get("id", ""))
        if not nid:
            continue
        rel = obsidian_relpaths(entry)
        milestone = str(entry.get("milestone", ""))
        ms = milestones.setdefault(
            milestone,
            {"moc": rel["milestone_moc"], "sidecar": rel["milestone_json"], "nodes": []},
        )
        if nid not in ms["nodes"]:
            ms["nodes"].append(nid)

        nodes[nid] = {
            "ast_layer": LAYER_NODES,
            "hub": rel["node_hub"],
            "sidecar": rel["index_json"],
            "skill": rel["skill"],
            "stage": str(entry.get("stage", "")),
            "group": str(entry.get("group", "")),
            "milestone": milestone,
            "graph": str(entry.get("graph", "verify_group")),
            "gates": {
                "check": rel["check"],
                "respond": rel["respond"],
                "milestone": rel["milestone"],
                "sidecar": rel["gate_json"],
            },
            "requires": list(entry.get("requires") or []),
        }
        for req in entry.get("requires") or []:
            edges.append({"from": str(req), "to": nid, "type": "requires"})

    return {
        "contract": "obsidian_ast_graph_v1",
        "project_id": project_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "index": f"{LAYER_INDEX}/PROJECT-MOC.md",
        "graph_json": f"{LAYER_INDEX}/graph.json",
        "layers": {
            "index": LAYER_INDEX,
            "milestones": LAYER_MILESTONES,
            "stages": LAYER_STAGES,
            "nodes": LAYER_NODES,
            "skills": LAYER_SKILLS,
            "intake": LAYER_INTAKE,
            "paper": LAYER_PAPER,
        },
        "intake": intake
        or {
            "moc": f"{LAYER_INTAKE}/SOURCES-MOC.md",
            "sidecar": f"{LAYER_INTAKE}/intake.json",
            "runtime_dir": "intake",
            "sources": [],
        },
        "milestones": milestones,
        "nodes": nodes,
        "edges": edges,
    }