"""Paper completion progress — mechanical %% + LLM judgment, Obsidian diagram maintenance."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml
from soc_verify.obsidian_md import LAYER_INDEX, LAYER_INTAKE, LAYER_PAPER, obsidian_frontmatter, wikilink
from soc_verify.paper_readiness import assess_paper_readiness


SPEC_NAME = "paper_progress_spec.yaml"
LAYER_PAPER = "06-paper"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_spec(root: Path) -> dict[str, Any]:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = _repo_root() / "registry" / SPEC_NAME
    return load_yaml(p) or {}


def resolve_paper_project(root: Path, campaign: str, project_id: str = "") -> str:
    if project_id:
        return project_id
    from soc_verify.experiment import find_runs_for_campaign

    runs = find_runs_for_campaign(root, campaign)
    if runs:
        counts = Counter(str(r.get("project_id", "")) for r in runs)
        return counts.most_common(1)[0][0]
    projects = root / "projects"
    if projects.is_dir():
        for cand in sorted(projects.iterdir()):
            if cand.is_dir() and (cand / "state.yaml").is_file():
                return cand.name
    return ""


def _intake_percent(project_dir: Path) -> tuple[float, list[str]]:
    gaps: list[str] = []
    score = 0.0
    intake_json = project_dir / "knowledge" / "obsidian" / LAYER_INTAKE / "intake.json"
    if intake_json.is_file():
        try:
            data = json.loads(intake_json.read_text(encoding="utf-8"))
            n = int(data.get("source_count") or len(data.get("sources") or []))
            score += min(1.0, n / 5.0) * 0.6
            if n < 3:
                gaps.append(f"intake: {n}/5 sources — add Confluence/wiki/md via knowledge sources")
        except json.JSONDecodeError:
            gaps.append("intake: invalid 05-intake/intake.json")
    else:
        gaps.append("intake: run soc-verify knowledge collect --project ID")

    if (project_dir / "intake" / "paper_intake_skills.json").is_file():
        score += 0.25
    else:
        gaps.append("intake: bootstrap paper skills (knowledge collect)")

    moc = project_dir / "knowledge" / "obsidian" / LAYER_INTAKE / "SOURCES-MOC.md"
    if moc.is_file():
        score += 0.15
    return round(min(1.0, score) * 100, 1), gaps


def _dim_map(report: dict[str, Any]) -> dict[str, float]:
    return {str(d.get("id", "")): float(d.get("score", 0)) for d in report.get("dimensions") or []}


def build_puzzle_pieces(
    report: dict[str, Any],
    project_dir: Path,
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    dims = _dim_map(report)
    pieces: list[dict[str, Any]] = []

    intake_pct, intake_gaps = _intake_percent(project_dir)
    pieces.append(
        {
            "id": "intake",
            "label_ko": "수집·정리",
            "percent": intake_pct,
            "missing": intake_gaps,
            "wikilink": f"{LAYER_INTAKE}/SOURCES-MOC",
        }
    )

    for stage in spec.get("pipeline_stages") or []:
        if not isinstance(stage, dict):
            continue
        sid = str(stage.get("id", ""))
        if sid in ("intake", "draft"):
            continue
        dim_ids = list(stage.get("dimensions") or [])
        if not dim_ids:
            continue
        scores = [dims.get(d, 0.0) for d in dim_ids]
        pct = round(sum(scores) / len(scores) * 100, 1)
        gaps: list[str] = []
        for d in report.get("dimensions") or []:
            if str(d.get("id")) in dim_ids:
                gaps.extend(list(d.get("gaps") or [])[:2])
        pieces.append(
            {
                "id": sid,
                "label_ko": str(stage.get("label_ko", sid)),
                "percent": pct,
                "missing": gaps[:4],
                "dimensions": dim_ids,
            }
        )

    sections = report.get("section_status") or []
    if sections:
        draft_pct = round(sum(float(s.get("readiness_percent", 0)) for s in sections) / len(sections), 1)
        draft_gaps = [
            f"{s.get('section')}: {s.get('readiness_percent')}%"
            for s in sections
            if not s.get("writable")
        ]
    else:
        draft_pct = float(report.get("overall_percent", 0))
        draft_gaps = ["section_status unavailable"]
    pieces.append(
        {
            "id": "draft",
            "label_ko": "논문 초안",
            "percent": draft_pct,
            "missing": draft_gaps[:5],
            "writable_sections": [s.get("section") for s in sections if s.get("writable")],
        }
    )
    return pieces


def build_mechanical_judgment(
    report: dict[str, Any],
    project_dir: Path,
    root: Path,
    *,
    campaign: str,
    project_id: str,
) -> dict[str, Any]:
    spec = load_spec(root)
    pieces = build_puzzle_pieces(report, project_dir, spec)
    section_gaps = [
        {
            "section": str(s.get("section", "")),
            "percent": float(s.get("readiness_percent", 0)),
            "writable": bool(s.get("writable")),
            "missing_ko": f"{s.get('section')} — {s.get('readiness_percent')}% (requires: {', '.join(s.get('requires') or [])})",
        }
        for s in report.get("section_status") or []
    ]
    top_gaps: list[str] = []
    for d in sorted(report.get("dimensions") or [], key=lambda x: float(x.get("score", 0))):
        for g in d.get("gaps") or []:
            top_gaps.append(str(g))
            if len(top_gaps) >= 5:
                break
        if len(top_gaps) >= 5:
            break
    for p in pieces:
        if float(p.get("percent", 0)) < 70:
            for m in p.get("missing") or []:
                if m not in top_gaps:
                    top_gaps.append(str(m))
                if len(top_gaps) >= 8:
                    break

    overall = float(report.get("overall_percent", 0))
    return {
        "contract": "paper_progress_judgment_v1",
        "source": "mechanical",
        "project_id": project_id,
        "campaign": campaign,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "overall_percent": overall,
        "mechanical_percent": overall,
        "llm_adjustment": 0,
        "verdict": report.get("verdict"),
        "paper_ready": report.get("paper_ready"),
        "llm_summary_ko": (
            f"기계 평가 기준 논문 준비도 {overall}%. "
            f"부족 차원: {', '.join(d.get('id', '') for d in sorted(report.get('dimensions') or [], key=lambda x: x.get('score', 0))[:3])}."
        ),
        "puzzle_pieces": pieces,
        "section_gaps": section_gaps,
        "top_gaps": top_gaps[:8],
        "next_commands": list(report.get("next_actions") or [])[:8],
    }


def load_llm_judgment(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "intake" / "paper_progress_judgment.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def merge_judgment(mechanical: dict[str, Any], llm: dict[str, Any] | None) -> dict[str, Any]:
    if not llm or llm.get("source") == "mechanical":
        return mechanical
    merged = {**mechanical, **llm}
    merged["mechanical_percent"] = mechanical.get("overall_percent")
    if "overall_percent" not in llm:
        merged["overall_percent"] = mechanical.get("overall_percent")
    merged["source"] = "mechanical+llm"
    if llm.get("puzzle_pieces"):
        merged["puzzle_pieces"] = llm["puzzle_pieces"]
    if llm.get("section_gaps"):
        merged["section_gaps"] = llm["section_gaps"]
    if llm.get("top_gaps"):
        merged["top_gaps"] = llm["top_gaps"]
    if llm.get("llm_summary_ko"):
        merged["llm_summary_ko"] = llm["llm_summary_ko"]
    return merged


def write_paper_progress_llm_prompt(
    project_dir: Path,
    root: Path,
    *,
    mechanical: dict[str, Any],
    readiness: dict[str, Any],
    campaign: str,
) -> Path:
    skill_path = project_dir / "skills" / "paper-progress-judge" / "SKILL.md"
    skill_excerpt = ""
    if skill_path.is_file():
        skill_excerpt = skill_path.read_text(encoding="utf-8")[:10000]
    else:
        tpl = _repo_root() / "templates" / "skills" / "paper-intake" / "paper-progress-judge" / "SKILL.md"
        if tpl.is_file():
            skill_excerpt = tpl.read_text(encoding="utf-8")[:10000]

    intake_ast: dict[str, Any] = {}
    intake_path = project_dir / "knowledge" / "obsidian" / LAYER_INTAKE / "intake.json"
    if intake_path.is_file():
        intake_ast = json.loads(intake_path.read_text(encoding="utf-8"))

    payload = {
        "task": "paper_progress_judge",
        "instruction": (
            "Judge how far the project is from a publishable paper draft. "
            "Update puzzle_pieces[].percent and missing[] with qualitative + quantitative gaps. "
            "Write llm_summary_ko in Korean for the user. Output paper_progress_judgment.json only."
        ),
        "project_id": project_dir.name,
        "campaign": campaign,
        "mechanical_readiness": readiness,
        "mechanical_judgment": mechanical,
        "intake_ast": intake_ast,
        "skill": skill_excerpt,
        "required_output": "intake/paper_progress_judgment.json",
        "output_schema": {
            "contract": "paper_progress_judgment_v1",
            "source": "llm",
            "overall_percent": "float 0-100",
            "llm_adjustment": "float vs mechanical",
            "puzzle_pieces": "[{id, label_ko, percent, missing[]}]",
            "section_gaps": "[{section, percent, missing_ko}]",
            "top_gaps": "string[]",
            "next_commands": "string[]",
            "llm_summary_ko": "string",
        },
    }
    out = project_dir / "intake" / "paper_progress_prompt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def render_progress_mermaid(judgment: dict[str, Any]) -> str:
    pieces = judgment.get("puzzle_pieces") or []
    if not pieces:
        return "flowchart LR\n  X[no data]"
    nodes: list[str] = []
    edges: list[str] = []
    for i, p in enumerate(pieces):
        nid = f"P{i}"
        label = str(p.get("label_ko", p.get("id", "")))
        pct = p.get("percent", 0)
        nodes.append(f'  {nid}["{label}<br/>{pct}%"]')
        if i > 0:
            edges.append(f"  P{i - 1} --> {nid}")
    style_lines = []
    for i, p in enumerate(pieces):
        pct = float(p.get("percent", 0))
        if pct >= 85:
            color = "#4ade80"
        elif pct >= 65:
            color = "#facc15"
        elif pct >= 40:
            color = "#fb923c"
        else:
            color = "#f87171"
        style_lines.append(f"  style P{i} fill:{color},color:#111")
    return "flowchart LR\n" + "\n".join(nodes + edges + style_lines)


def render_paper_progress_note(
    project_id: str,
    judgment: dict[str, Any],
    *,
    campaign: str,
) -> str:
    overall = judgment.get("overall_percent", 0)
    mechanical = judgment.get("mechanical_percent", overall)
    source = judgment.get("source", "mechanical")
    fm = obsidian_frontmatter(
        {
            "type": "paper_progress",
            "ast_layer": LAYER_PAPER,
            "project_id": project_id,
            "campaign": campaign,
            "overall_percent": overall,
            "mechanical_percent": mechanical,
            "paper_ready": judgment.get("paper_ready"),
            "tags": [f"project/{project_id}", "paper", "progress"],
        }
    )
    mermaid = render_progress_mermaid(judgment)

    piece_rows = []
    for p in judgment.get("puzzle_pieces") or []:
        bar = "█" * int(float(p.get("percent", 0)) / 10) + "░" * (10 - int(float(p.get("percent", 0)) / 10))
        missing = "; ".join(p.get("missing") or []) or "(none)"
        piece_rows.append(f"| {p.get('label_ko')} | {p.get('percent')}% | `{bar}` | {missing} |")

    section_rows = []
    for s in judgment.get("section_gaps") or []:
        mark = "✓" if s.get("writable") else "○"
        section_rows.append(
            f"| {mark} {s.get('section')} | {s.get('percent')}% | {s.get('missing_ko', '')} |"
        )

    gap_lines = "\n".join(f"- {g}" for g in judgment.get("top_gaps") or []) or "(none)"
    cmd_lines = "\n".join(f"```bash\n{c}\n```" for c in judgment.get("next_commands") or []) or "(none)"

    body = f"""# Paper Progress — {project_id}

태그: `#paper` `#progress` · 캠페인: `{campaign}`
상위: {wikilink(LAYER_INDEX, 'PROJECT-MOC')} · 수집: {wikilink(LAYER_INTAKE, 'SOURCES-MOC')}

---

## 한 줄 요약 (LLM)

{judgment.get('llm_summary_ko', '(pending LLM judgment)')}

**전체 {overall}%** (기계 {mechanical}% · 판단 출처: `{source}`) — `{judgment.get('verdict', '')}`  
paper_ready: **{judgment.get('paper_ready')}**

---

## 논문 완성 퍼즐 (%% 유지)

```mermaid
{mermaid}
```

> LLM이 `intake/paper_progress_judgment.json` 을 갱신할 때마다 이 다이어그램이 sync 됩니다.

## 단계별 현황

| 단계 | %% | bar | 부족 |
|------|-----|-----|------|
{chr(10).join(piece_rows) or '| — | — | — | — |'}

## 논문 섹션

| | 섹션 | %% | 부족 |
|---|------|-----|------|
{chr(10).join(section_rows) or '| — | — | — |'}

## Top gaps

{gap_lines}

## Next commands

{cmd_lines}

## LLM 작업

```bash
soc-verify paper progress --project {project_id} --campaign {campaign} --write
# → intake/paper_progress_prompt.json 생성 후 LLM이 judgment JSON 작성
```
"""
    return fm + "\n\n" + body


def sync_paper_progress(
    root: Path,
    project_id: str,
    campaign: str,
    *,
    write_llm_prompt: bool = True,
    force_mechanical_judgment: bool = False,
) -> dict[str, Any]:
    """Refresh 06-paper/PROGRESS.md + paper_progress.json from readiness + judgment."""
    root = root.resolve()
    project_dir = root / "projects" / project_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"project not found: {project_id}")

    readiness = assess_paper_readiness(root, campaign)
    mechanical = build_mechanical_judgment(
        readiness, project_dir, root, campaign=campaign, project_id=project_id
    )

    judgment_path = project_dir / "intake" / "paper_progress_judgment.json"
    if force_mechanical_judgment or not judgment_path.is_file():
        judgment_path.parent.mkdir(parents=True, exist_ok=True)
        judgment_path.write_text(json.dumps(mechanical, indent=2, ensure_ascii=False), encoding="utf-8")

    llm = load_llm_judgment(project_dir)
    merged = merge_judgment(mechanical, llm)

    if write_llm_prompt:
        write_paper_progress_llm_prompt(
            project_dir, root, mechanical=mechanical, readiness=readiness, campaign=campaign
        )

    paper_dir = project_dir / "knowledge" / "obsidian" / LAYER_PAPER
    paper_dir.mkdir(parents=True, exist_ok=True)
    progress_md = paper_dir / "PROGRESS.md"
    progress_md.write_text(
        render_paper_progress_note(project_id, merged, campaign=campaign),
        encoding="utf-8",
    )

    progress_json = {
        "contract": "paper_progress_v1",
        "project_id": project_id,
        "campaign": campaign,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "overall_percent": merged.get("overall_percent"),
        "mechanical_percent": merged.get("mechanical_percent"),
        "paper_ready": merged.get("paper_ready"),
        "verdict": merged.get("verdict"),
        "judgment_source": merged.get("source"),
        "progress_md": f"{LAYER_PAPER}/PROGRESS.md",
        "puzzle_pieces": merged.get("puzzle_pieces"),
        "section_gaps": merged.get("section_gaps"),
        "top_gaps": merged.get("top_gaps"),
        "readiness_ref": f"exports/{campaign}/paper_readiness.json",
        "llm_prompt": "intake/paper_progress_prompt.json",
        "llm_judgment": "intake/paper_progress_judgment.json",
    }
    json_path = paper_dir / "paper_progress.json"
    json_path.write_text(json.dumps(progress_json, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "project_id": project_id,
        "campaign": campaign,
        "overall_percent": merged.get("overall_percent"),
        "progress_md": str(progress_md.relative_to(project_dir)),
        "progress_json": str(json_path.relative_to(project_dir)),
        "llm_prompt": "intake/paper_progress_prompt.json",
    }


def apply_llm_judgment(project_dir: Path, data: dict[str, Any]) -> Path:
    """Persist LLM-authored judgment and re-sync PROGRESS.md if root known."""
    data = {**data, "contract": "paper_progress_judgment_v1", "source": data.get("source", "llm")}
    path = project_dir / "intake" / "paper_progress_judgment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path