"""Paper factory — portable orchestration (CLI, scripts, any LLM environment)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.experiment import evaluation_progress, find_runs_for_campaign, load_evaluation_manifest
from soc_verify.paper_export import export_paper
from soc_verify.paper_readiness import (
    assess_paper_readiness,
    format_readiness_summary,
    load_readiness_spec,
    write_readiness_report,
)


def find_repo_root(start: Path | None = None) -> Path:
    """Locate soc-verify-agent root from cwd or script location."""
    here = (start or Path.cwd()).resolve()
    for p in [here, *here.parents]:
        if (p / "registry" / "paper_readiness_spec.yaml").is_file():
            return p
        if (p / "pyproject.toml").is_file() and (p / "src" / "soc_verify").is_dir():
            return p
    return here


@dataclass
class VerifySuggestion:
    project_id: str
    stage: str
    group: str
    condition: str
    campaign: str
    hypothesis: str
    reason: str

    def to_command(self, root: Path | None = None) -> str:
        root_flag = f"--root {root} " if root else ""
        return (
            f"soc-verify {root_flag}verify {self.project_id} {self.stage} {self.group} "
            f"--campaign {self.campaign} --condition {self.condition} --hypothesis {self.hypothesis}"
        )


@dataclass
class PaperFactoryReport:
    campaign: str
    readiness: dict[str, Any]
    suggestions: list[VerifySuggestion] = field(default_factory=list)
    export_result: dict[str, Any] | None = None
    written_paths: list[str] = field(default_factory=list)

    @property
    def overall_percent(self) -> float:
        return float(self.readiness.get("overall_percent", 0))

    @property
    def paper_ready(self) -> bool:
        return bool(self.readiness.get("paper_ready"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "paper_factory_report_v1",
            "campaign": self.campaign,
            "overall_percent": self.overall_percent,
            "paper_ready": self.paper_ready,
            "verdict": self.readiness.get("verdict"),
            "readiness": self.readiness,
            "suggestions": [
                {
                    "command": s.to_command(),
                    "condition": s.condition,
                    "reason": s.reason,
                    "project_id": s.project_id,
                    "stage": s.stage,
                    "group": s.group,
                }
                for s in self.suggestions
            ],
            "export_result": self.export_result,
            "written_paths": self.written_paths,
        }


def _resolve_gates(root: Path) -> list[dict[str, Any]]:
    manifest = load_evaluation_manifest(root)
    gates: list[dict[str, Any]] = []
    for g in manifest.get("gates") or []:
        if not isinstance(g, dict):
            continue
        pid = str(g.get("project_id", ""))
        if not (root / "projects" / pid).is_dir():
            continue
        gates.append(g)
    if not gates:
        gates.append(
            {"project_id": "EXAMPLE-SOC", "stage": "simulation", "group": "gpio_ext", "role": "default"}
        )
    return gates


def suggest_verify_commands(
    root: Path,
    campaign: str,
    *,
    hypothesis: str = "H1",
    max_per_condition: int = 3,
    readiness: dict[str, Any] | None = None,
) -> list[VerifySuggestion]:
    """Build verify commands to close experiment_design gaps."""
    root = root.resolve()
    report = readiness or assess_paper_readiness(root, campaign)
    spec = load_readiness_spec(root)
    thr = spec.get("thresholds") or {}
    min_per = int(thr.get("min_runs_per_condition", 5))
    required = list(spec.get("required_conditions") or ["control", "treatment_full"])
    conditions = report.get("conditions") or {}
    gates = _resolve_gates(root)
    gate = gates[0]

    out: list[VerifySuggestion] = []
    for cond in required:
        have = int(conditions.get(cond, 0))
        need = max(0, min_per - have)
        for _ in range(min(need, max_per_condition)):
            out.append(
                VerifySuggestion(
                    project_id=str(gate["project_id"]),
                    stage=str(gate["stage"]),
                    group=str(gate["group"]),
                    condition=cond,
                    campaign=campaign,
                    hypothesis=hypothesis,
                    reason=f"{cond}: {have}/{min_per} runs",
                )
            )
    return out


def format_suggestions_text(
    suggestions: list[VerifySuggestion],
    *,
    root: Path | None = None,
    campaign: str = "",
    overall_percent: float | None = None,
    verdict: str | None = None,
) -> str:
    lines: list[str] = []
    if campaign:
        pct = f"{overall_percent}%" if overall_percent is not None else "?"
        v = verdict or ""
        lines.extend([f"# Paper gaps — campaign {campaign}", f"# Readiness: {pct} ({v})", ""])

    by_cond: dict[str, list[VerifySuggestion]] = {}
    for s in suggestions:
        by_cond.setdefault(s.condition, []).append(s)

    for cond, cmds in by_cond.items():
        if not cmds:
            continue
        reason = cmds[0].reason
        lines.append(f"# {cond}: {reason}")
        for s in cmds:
            lines.append(s.to_command(root))
        lines.append("")

    if root and campaign:
        lines.append("# When data sufficient:")
        lines.append(f"soc-verify --root {root} export-paper --campaign {campaign}")

    return "\n".join(lines).rstrip() + "\n"


def run_factory(
    root: Path,
    campaign: str,
    *,
    hypothesis: str = "H1",
    write: bool = False,
    export: bool = False,
    max_suggestions: int = 3,
) -> PaperFactoryReport:
    """Assess readiness, suggest commands, optionally write reports and export."""
    root = root.resolve()
    readiness = assess_paper_readiness(root, campaign)
    suggestions = suggest_verify_commands(
        root,
        campaign,
        hypothesis=hypothesis,
        max_per_condition=max_suggestions,
        readiness=readiness,
    )
    result = PaperFactoryReport(campaign=campaign, readiness=readiness, suggestions=suggestions)

    if write:
        json_path = write_readiness_report(root, campaign)
        md_path = json_path.with_suffix(".md")
        md_path.write_text(format_readiness_summary(readiness), encoding="utf-8")
        result.written_paths.extend([str(json_path), str(md_path)])

        suggest_path = root / "exports" / campaign / "suggested_commands.sh"
        suggest_path.parent.mkdir(parents=True, exist_ok=True)
        suggest_path.write_text(
            format_suggestions_text(
                suggestions,
                root=root,
                campaign=campaign,
                overall_percent=result.overall_percent,
                verdict=str(readiness.get("verdict", "")),
            ),
            encoding="utf-8",
        )
        result.written_paths.append(str(suggest_path))

        try:
            from soc_verify.paper_progress import resolve_paper_project, sync_paper_progress

            pid = resolve_paper_project(root, campaign)
            if pid:
                sync_paper_progress(root, pid, campaign, write_llm_prompt=True)
                result.written_paths.append(
                    f"projects/{pid}/knowledge/obsidian/06-paper/PROGRESS.md"
                )
        except (FileNotFoundError, OSError, ValueError):
            pass

    if export or (export is False and result.paper_ready):
        if export or result.paper_ready:
            out_dir = root / "exports" / campaign
            result.export_result = export_paper(root, campaign, out_dir)
            if result.export_result:
                for f in result.export_result.get("files") or []:
                    result.written_paths.append(str(out_dir / f))

    return result


def format_factory_summary(report: PaperFactoryReport) -> str:
    """Human-readable one-page summary for terminal or LLM context."""
    r = report.readiness
    lines = [
        format_readiness_summary(r),
        "",
        "## Suggested verify commands",
        "",
    ]
    if report.suggestions:
        lines.append(format_suggestions_text(report.suggestions, root=None, campaign="").strip())
    else:
        lines.append("(experiment design thresholds met)")
    if report.export_result:
        lines.extend(
            [
                "",
                "## Export",
                "",
                f"Exported to {report.export_result.get('out_dir')} "
                f"({report.export_result.get('run_count')} runs, "
                f"readiness {report.export_result.get('paper_readiness_percent')}%)",
            ]
        )
    if report.written_paths:
        lines.extend(["", "## Written files", ""])
        for p in report.written_paths:
            lines.append(f"- {p}")
    return "\n".join(lines)