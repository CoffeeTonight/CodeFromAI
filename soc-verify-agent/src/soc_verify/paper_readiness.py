"""Paper readiness — % complete, gaps, section status for publication."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from soc_verify.experiment import (
    evaluation_progress,
    find_runs_for_campaign,
    load_evaluation_manifest,
    load_experiment_run,
)
from soc_verify.llm_telemetry import load_llm_telemetry
from soc_verify.models import load_yaml
from soc_verify.platform_telemetry import baseline_path, code_change_summary, load_cumulative_stats


SPEC_NAME = "paper_readiness_spec.yaml"


def load_readiness_spec(root: Path) -> dict[str, Any]:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return load_yaml(p)


@dataclass
class DimensionScore:
    id: str
    label: str
    weight: float
    score: float  # 0..1
    met: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "weight": self.weight,
            "score": round(self.score, 4),
            "weighted": round(self.score * self.weight, 4),
            "met": self.met,
            "gaps": self.gaps,
        }


def _find_export_dir(root: Path, campaign: str) -> Path | None:
    """Locate export-paper output for a campaign."""
    preferred = root / "exports" / campaign
    if (preferred / "methods.json").is_file():
        return preferred
    exports = root / "exports"
    if not exports.is_dir():
        return None
    for sub in sorted(exports.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not sub.is_dir():
            continue
        methods = sub / "methods.json"
        if not methods.is_file():
            continue
        try:
            data = json.loads(methods.read_text(encoding="utf-8"))
            if data.get("campaign") == campaign:
                return sub
        except json.JSONDecodeError:
            continue
    return preferred if preferred.is_dir() else None


def _run_artifacts(run_dir: Path) -> dict[str, bool]:
    names = (
        "experiment_run.json",
        "improvement_snapshot.json",
        "branch_scorecard.json",
        "improvement_ablation.json",
        "env_pin.json",
        "repro_bundle.tar.gz",
        "llm_telemetry.jsonl",
        "child_graph_evidence.json",
    )
    return {n: (run_dir / n).is_file() for n in names}


def assess_paper_readiness(root: Path, campaign: str) -> dict[str, Any]:
    root = root.resolve()
    spec = load_readiness_spec(root)
    weights = spec.get("weights") or {}
    thr = spec.get("thresholds") or {}
    required_conds = list(spec.get("required_conditions") or ["control", "treatment_full"])

    runs = find_runs_for_campaign(root, campaign)
    run_dirs = [Path(r["run_dir"]) for r in runs]

    by_condition: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        cond = str((r.get("experiment") or {}).get("condition", "unknown"))
        by_condition.setdefault(cond, []).append(r)

    min_per = int(thr.get("min_runs_per_condition", 5))
    min_total = int(thr.get("min_total_runs", 10))
    min_conds = int(thr.get("min_conditions", 2))

    # --- experiment_design ---
    exp_gaps: list[str] = []
    exp_met: list[str] = []
    cond_scores: list[float] = []
    for cond in required_conds:
        n = len(by_condition.get(cond, []))
        cond_scores.append(min(1.0, n / max(1, min_per)))
        if n >= min_per:
            exp_met.append(f"{cond}: {n} runs (>={min_per})")
        else:
            exp_gaps.append(f"{cond}: need {min_per - n} more runs (have {n})")
    present_conds = len([c for c in required_conds if by_condition.get(c)])
    cond_coverage = present_conds / max(1, min_conds)
    total_coverage = min(1.0, len(runs) / max(1, min_total))
    exp_score = 0.5 * (sum(cond_scores) / max(1, len(cond_scores))) + 0.3 * cond_coverage + 0.2 * total_coverage
    if len(runs) >= min_total:
        exp_met.append(f"total runs: {len(runs)} (>={min_total})")
    else:
        exp_gaps.append(f"total runs: need {min_total - len(runs)} more (have {len(runs)})")

    # --- evaluation_gates ---
    prog = evaluation_progress(root, campaign)
    gates_total = int(prog.get("gates_total", 0))
    gates_pass = int(prog.get("gates_passing", 0))
    gate_ratio = gates_pass / max(1, gates_total)
    min_gate_ratio = float(thr.get("min_gates_passing_ratio", 0.8))
    eval_score = min(1.0, gate_ratio / min_gate_ratio) if min_gate_ratio else gate_ratio
    eval_met = [f"evaluation gates: {gates_pass}/{gates_total} passing criteria"]
    eval_gaps = []
    for g in prog.get("gates") or []:
        if not g.get("project_present"):
            eval_gaps.append(f"gate missing project: {g.get('project_id')}")
        elif not g.get("evaluated"):
            eval_gaps.append(f"gate not run: {g.get('project_id')}/{g.get('stage')}/{g.get('group')}")
        elif not g.get("criteria_ok"):
            eval_gaps.append(
                f"gate criteria fail: {g.get('project_id')}/{g.get('stage')}/{g.get('group')} "
                f"verdict={g.get('verdict')} idx={g.get('improvement_index')}"
            )

    # --- telemetry_baseline ---
    base = load_yaml(baseline_path(root))
    cum = load_cumulative_stats(root)
    tel_met: list[str] = []
    tel_gaps: list[str] = []
    tel_parts: list[float] = []
    if base.get("first_started_at"):
        tel_met.append(f"baseline since {str(base.get('first_started_at'))[:10]}")
        tel_parts.append(1.0)
    else:
        tel_gaps.append("run any soc-verify command to establish platform_baseline.yaml")
        tel_parts.append(0.0)
    uses = int(cum.get("total_uses", 0))
    tel_parts.append(min(1.0, uses / max(1, min_total)))
    if uses >= min_total:
        tel_met.append(f"platform uses: {uses}")
    else:
        tel_gaps.append(f"platform uses: {uses}/{min_total}")
    tel_score = sum(tel_parts) / len(tel_parts)

    # --- llm_provenance ---
    llm_runs = 0
    llm_with_tel = 0
    total_invocations = 0
    for rd in run_dirs:
        inv = load_llm_telemetry(rd)
        if inv:
            llm_with_tel += 1
            total_invocations += len(inv)
        exp = load_experiment_run(rd)
        if exp:
            llm_runs += 1
    cov = llm_with_tel / max(1, len(run_dirs))
    min_cov = float(thr.get("min_llm_telemetry_coverage", 0.5))
    llm_score = min(1.0, cov / min_cov) if min_cov else cov
    llm_met = [f"llm_telemetry on {llm_with_tel}/{len(run_dirs)} runs, {total_invocations} invocations"]
    llm_gaps = []
    if cov < min_cov:
        llm_gaps.append(f"llm_telemetry coverage {cov:.0%} < {min_cov:.0%} — use openai_compatible or log stubs")

    # --- self_improvement ---
    ablation_linked = 0
    has_scorecard = 0
    has_ablation = 0
    for rd in run_dirs:
        arts = _run_artifacts(rd)
        if arts.get("branch_scorecard.json"):
            has_scorecard += 1
        if arts.get("improvement_ablation.json"):
            has_ablation += 1
            try:
                ab = json.loads((rd / "improvement_ablation.json").read_text(encoding="utf-8"))
                if ab.get("linked_proposal"):
                    ablation_linked += 1
            except json.JSONDecodeError:
                pass
    min_abl = int(thr.get("min_ablation_linked", 3))
    code = code_change_summary(root)
    min_code = int(thr.get("min_code_changes", 5))
    si_parts = [
        min(1.0, has_scorecard / max(1, len(run_dirs))),
        min(1.0, ablation_linked / max(1, min_abl)),
        min(1.0, int(code.get("total", 0)) / max(1, min_code)),
    ]
    si_score = sum(si_parts) / len(si_parts)
    si_met = [
        f"branch_scorecards: {has_scorecard}/{len(run_dirs)}",
        f"ablation linked: {ablation_linked}",
        f"code changes logged: {code.get('total', 0)}",
    ]
    si_gaps = []
    if ablation_linked < min_abl:
        si_gaps.append(f"need {min_abl - ablation_linked} more ablation runs with linked proposals")
    if int(code.get("total", 0)) < min_code:
        si_gaps.append(f"code_change_log: {code.get('total', 0)}/{min_code}")

    # --- reproducibility ---
    repro_ok = sum(1 for rd in run_dirs if (rd / "repro_bundle.tar.gz").is_file())
    env_ok = sum(1 for rd in run_dirs if (rd / "env_pin.json").is_file())
    doc_ok = (root / "templates" / "obsidian" / "11-LANGGRAPH-SUMMARY.md").is_file()
    rep_parts = [
        min(1.0, repro_ok / max(1, len(run_dirs))) if run_dirs else 0.0,
        min(1.0, env_ok / max(1, len(run_dirs))) if run_dirs else 0.0,
        1.0 if doc_ok else 0.0,
    ]
    rep_score = sum(rep_parts) / len(rep_parts)
    rep_met = [f"repro_bundle: {repro_ok}/{len(run_dirs)}", f"env_pin: {env_ok}/{len(run_dirs)}"]
    rep_gaps = []
    if not doc_ok:
        rep_gaps.append("missing templates/obsidian/11-LANGGRAPH-SUMMARY.md")
    if run_dirs and repro_ok < len(run_dirs):
        rep_gaps.append(f"{len(run_dirs) - repro_ok} runs missing repro_bundle (complete meta_score)")

    # --- export_artifacts ---
    export_dir = _find_export_dir(root, campaign)
    export_files = ["runs.csv", "methods.md", "methods.json"]
    export_found = (
        sum(1 for f in export_files if (export_dir / f).is_file()) if export_dir else 0
    )
    exp_art_score = export_found / len(export_files)
    export_label = str(export_dir.relative_to(root)) if export_dir else f"exports/{campaign}"
    exp_art_met = [f"export: {export_found}/{len(export_files)} files in {export_label}"]
    exp_art_gaps = []
    if exp_art_score < 1.0:
        exp_art_gaps.append(f"run: soc-verify --root . export-paper --campaign {campaign}")

    dimensions = [
        DimensionScore("experiment_design", "Experiment design (A/B runs)", float(weights.get("experiment_design", 0.2)), exp_score, exp_met, exp_gaps),
        DimensionScore("evaluation_gates", "Evaluation gate pass rate", float(weights.get("evaluation_gates", 0.2)), eval_score, eval_met, eval_gaps),
        DimensionScore("telemetry_baseline", "Platform telemetry baseline", float(weights.get("telemetry_baseline", 0.15)), tel_score, tel_met, tel_gaps),
        DimensionScore("llm_provenance", "LLM provenance", float(weights.get("llm_provenance", 0.1)), llm_score, llm_met, llm_gaps),
        DimensionScore("self_improvement", "Self-improvement / ablation", float(weights.get("self_improvement", 0.15)), si_score, si_met, si_gaps),
        DimensionScore("reproducibility", "Reproducibility bundle", float(weights.get("reproducibility", 0.1)), rep_score, rep_met, rep_gaps),
        DimensionScore("export_artifacts", "Paper export artifacts", float(weights.get("export_artifacts", 0.1)), exp_art_score, exp_art_met, exp_art_gaps),
    ]

    overall = sum(d.score * d.weight for d in dimensions)
    overall_pct = round(overall * 100, 1)

    section_status = _section_readiness(spec, dimensions, overall_pct)

    next_actions = _prioritize_actions(dimensions, campaign)

    return {
        "contract": "paper_readiness_v1",
        "campaign": campaign,
        "assessed_at": datetime.now().isoformat(),
        "overall_score": round(overall, 4),
        "overall_percent": overall_pct,
        "paper_ready": overall_pct >= 85.0 and eval_score >= 0.8 and exp_score >= 0.7,
        "verdict": _verdict(overall_pct),
        "run_count": len(runs),
        "conditions": {k: len(v) for k, v in by_condition.items()},
        "dimensions": [d.to_dict() for d in dimensions],
        "evaluation_progress": prog,
        "section_status": section_status,
        "next_actions": next_actions,
        "typical_paper_reference": _typical_reference(),
    }


def _verdict(pct: float) -> str:
    if pct >= 85:
        return "ready_for_draft"
    if pct >= 65:
        return "collect_more_data"
    if pct >= 40:
        return "early_stage"
    return "bootstrap"


def _section_readiness(spec: dict[str, Any], dims: list[DimensionScore], overall_pct: float) -> list[dict[str, Any]]:
    dim_map = {d.id: d.score for d in dims}
    out: list[dict[str, Any]] = []
    for sec in spec.get("paper_sections") or []:
        if not isinstance(sec, dict):
            continue
        reqs = list(sec.get("requires") or [])
        if not reqs:
            score = min(1.0, overall_pct / 100.0)
        else:
            score = sum(dim_map.get(r, 0.0) for r in reqs) / len(reqs)
        out.append(
            {
                "section": sec.get("id"),
                "readiness_percent": round(score * 100, 1),
                "requires": reqs,
                "writable": score >= 0.7,
            }
        )
    return out


def _prioritize_actions(dims: list[DimensionScore], campaign: str) -> list[str]:
    actions: list[str] = []
    for d in sorted(dims, key=lambda x: x.score):
        if d.gaps:
            actions.extend(d.gaps[:2])
    if not any("export-paper" in a for a in actions):
        actions.append(f"soc-verify --root . export-paper --campaign {campaign}")
    return actions[:8]


def _typical_reference() -> dict[str, Any]:
    """What comparable systems papers usually report."""
    return {
        "systems_paper": {
            "architecture_diagram": "11-LANGGRAPH-SUMMARY.md",
            "baseline_comparison": "control vs treatment_full (>=5 each)",
            "case_study_runs": ">=10 total tagged runs",
            "repro_bundle": "per representative run",
        },
        "empirical_paper": {
            "evaluation_gates": ">=80% manifest gates pass criteria",
            "metrics": "improvement_index, trust, success_rate, parity",
            "ablation": ">=3 proposal-linked before/after pairs",
            "llm_details": "model, tokens, latency in llm_telemetry.jsonl",
        },
        "artifact_evaluation": {
            "env_pin": "git SHA + pip hash + config SHA256",
            "export": "runs.csv + methods.md for campaign",
        },
    }


def write_readiness_report(root: Path, campaign: str, out_path: Path | None = None) -> Path:
    report = assess_paper_readiness(root, campaign)
    if out_path is None:
        out_dir = root / "exports" / campaign
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "paper_readiness.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def format_readiness_summary(report: dict[str, Any]) -> str:
    lines = [
        f"# Paper readiness — {report.get('campaign')}",
        "",
        f"**{report.get('overall_percent')}%** — {report.get('verdict')} "
        f"({'READY' if report.get('paper_ready') else 'NOT YET'})",
        "",
        f"Runs tagged: {report.get('run_count')} | Conditions: {report.get('conditions')}",
        "",
        "## Dimensions",
        "",
    ]
    for d in report.get("dimensions") or []:
        bar = "█" * int(d.get("score", 0) * 10) + "░" * (10 - int(d.get("score", 0) * 10))
        lines.append(f"- **{d.get('label')}** [{bar}] {d.get('score', 0)*100:.0f}%")
        for g in d.get("gaps") or []:
            lines.append(f"  - gap: {g}")
    lines.extend(["", "## Next actions", ""])
    for i, a in enumerate(report.get("next_actions") or [], 1):
        lines.append(f"{i}. {a}")
    lines.extend(["", "## Section writability", ""])
    for s in report.get("section_status") or []:
        mark = "✓" if s.get("writable") else "○"
        lines.append(f"- {mark} {s.get('section')}: {s.get('readiness_percent')}%")
    return "\n".join(lines)