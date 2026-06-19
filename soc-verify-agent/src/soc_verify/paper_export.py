"""Paper factory export — campaign → CSV + Methods tables for publication."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.experiment import evaluation_progress, find_runs_for_campaign, load_evaluation_manifest
from soc_verify.llm_telemetry import load_llm_telemetry
from soc_verify.paper_readiness import assess_paper_readiness, format_readiness_summary
from soc_verify.platform_telemetry import code_change_summary, load_cumulative_stats


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _collect_run_row(root: Path, run_info: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(run_info["run_dir"])
    exp = run_info.get("experiment") or {}
    snap = _read_json(run_dir / "improvement_snapshot.json") or {}
    ablation = _read_json(run_dir / "improvement_ablation.json") or {}
    scorecard = _read_json(run_dir / "branch_scorecard.json") or {}
    user_fb = _read_json(run_dir / "user_feedback.json") or {}
    qqual = _read_json(run_dir / "question_quality.json") or {}
    env_pin = _read_json(run_dir / "env_pin.json") or {}

    llm_calls = load_llm_telemetry(run_dir)
    total_tokens = sum(int(x.get("total_tokens") or 0) for x in llm_calls)

    branches = scorecard.get("branches") or []
    mean_success = (
        sum(float(b.get("success_rate", 0)) for b in branches) / len(branches) if branches else None
    )

    return {
        "campaign": exp.get("campaign"),
        "condition": exp.get("condition"),
        "hypothesis": exp.get("hypothesis"),
        "project_id": run_info.get("project_id"),
        "run_id": run_info.get("run_id"),
        "stage": snap.get("stage", ""),
        "group": snap.get("group", ""),
        "verdict": snap.get("verdict"),
        "improvement_index": snap.get("improvement_index"),
        "trust_score": snap.get("trust_score"),
        "completeness": snap.get("completeness"),
        "mean_branch_success": mean_success,
        "branch_count": scorecard.get("branch_count"),
        "llm_invocations": len(llm_calls),
        "llm_total_tokens": total_tokens or None,
        "ablation_linked": bool(ablation.get("linked_proposal")),
        "delta_improvement_index": (ablation.get("delta_vs_previous_run") or {}).get("improvement_index"),
        "user_feedback_score": user_fb.get("overall_score"),
        "question_sharpness": qqual.get("mean_sharpness"),
        "git_commit": (env_pin.get("git") or {}).get("commit"),
        "config_sha256": env_pin.get("config_json_sha256"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def build_methods_payload(root: Path, campaign: str, run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    eval_m = load_evaluation_manifest(root)
    progress = evaluation_progress(root, campaign)
    cum = load_cumulative_stats(root)
    code = code_change_summary(root)

    by_condition: dict[str, list[dict[str, Any]]] = {}
    for r in run_rows:
        by_condition.setdefault(str(r.get("condition", "")), []).append(r)

    condition_stats = {}
    for cond, rows in by_condition.items():
        passes = sum(1 for r in rows if r.get("verdict") == "PASS")
        condition_stats[cond] = {
            "n_runs": len(rows),
            "pass_rate": round(passes / max(1, len(rows)), 4),
            "mean_improvement_index": round(
                sum(float(r.get("improvement_index") or 0) for r in rows) / max(1, len(rows)),
                4,
            ),
            "mean_trust": round(
                sum(float(r.get("trust_score") or 0) for r in rows) / max(1, len(rows)),
                4,
            ),
        }

    return {
        "contract": "paper_methods_v1",
        "generated_at": date.today().isoformat(),
        "campaign": campaign,
        "paper_title_slug": eval_m.get("paper_title_slug"),
        "evaluation_progress": progress,
        "platform_cumulative": cum,
        "code_changes": code,
        "condition_stats": condition_stats,
        "run_count": len(run_rows),
    }


def render_methods_md(methods: dict[str, Any]) -> str:
    prog = methods.get("evaluation_progress") or {}
    cum = methods.get("platform_cumulative") or {}
    cond = methods.get("condition_stats") or {}
    lines = [
        f"# Methods (auto-generated) — campaign `{methods.get('campaign')}`",
        "",
        f"Generated: {methods.get('generated_at')}",
        "",
        "## Platform",
        "",
        f"- Baseline uses since first start: {cum.get('total_uses', 0)}",
        f"- Cumulative pass rate: {cum.get('success_rate')}",
        f"- Code edits logged: {(methods.get('code_changes') or {}).get('total', 0)}",
        "",
        "## Evaluation set",
        "",
        f"- Gates passing criteria: {prog.get('gates_passing')}/{prog.get('gates_total')}",
        "",
        "## Conditions",
        "",
    ]
    for name, st in cond.items():
        lines.append(
            f"- **{name}**: n={st.get('n_runs')}, pass_rate={st.get('pass_rate')}, "
            f"mean improvement_index={st.get('mean_improvement_index')}, mean trust={st.get('mean_trust')}"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- Per-run: `experiment_run.json`, `improvement_snapshot.json`, `branch_scorecard.json`",
            "- LLM: `llm_telemetry.jsonl`",
            "- Repro: `repro_bundle.tar.gz`, `env_pin.json`",
            "",
        ]
    )
    return "\n".join(lines)


def export_paper(root: Path, campaign: str, out_dir: Path) -> dict[str, Any]:
    """Export all campaign runs to paper-ready CSV + Methods."""
    root = root.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = find_runs_for_campaign(root, campaign)
    run_rows = [_collect_run_row(root, r) for r in runs]

    branch_rows: list[dict[str, Any]] = []
    llm_rows: list[dict[str, Any]] = []
    for r in runs:
        run_dir = Path(r["run_dir"])
        exp = r.get("experiment") or {}
        sc = _read_json(run_dir / "branch_scorecard.json") or {}
        for b in sc.get("branches") or []:
            branch_rows.append(
                {
                    "campaign": exp.get("campaign"),
                    "condition": exp.get("condition"),
                    "run_id": r["run_id"],
                    "project_id": r["project_id"],
                    **{k: b.get(k) for k in ("branch_id", "success_rate", "trust_score", "retry_count")},
                }
            )
        for i, llm in enumerate(load_llm_telemetry(run_dir)):
            llm_rows.append(
                {
                    "campaign": exp.get("campaign"),
                    "run_id": r["run_id"],
                    "project_id": r["project_id"],
                    "invocation_index": i,
                    **{k: llm.get(k) for k in ("node", "task", "mode", "model", "latency_ms", "total_tokens", "invoked")},
                }
            )

    _write_csv(out_dir / "runs.csv", run_rows)
    _write_csv(out_dir / "branches.csv", branch_rows)
    _write_csv(out_dir / "llm_invocations.csv", llm_rows)

    methods = build_methods_payload(root, campaign, run_rows)
    (out_dir / "methods.json").write_text(json.dumps(methods, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "methods.md").write_text(render_methods_md(methods), encoding="utf-8")
    (out_dir / "evaluation_progress.json").write_text(
        json.dumps(methods.get("evaluation_progress"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    readiness = assess_paper_readiness(root, campaign)
    (out_dir / "paper_readiness.json").write_text(
        json.dumps(readiness, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "paper_readiness.md").write_text(
        format_readiness_summary(readiness),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "campaign": campaign,
        "out_dir": str(out_dir),
        "run_count": len(run_rows),
        "branch_rows": len(branch_rows),
        "llm_rows": len(llm_rows),
        "paper_readiness_percent": readiness.get("overall_percent"),
        "paper_ready": readiness.get("paper_ready"),
        "files": [
            "runs.csv",
            "branches.csv",
            "llm_invocations.csv",
            "methods.json",
            "methods.md",
            "evaluation_progress.json",
            "paper_readiness.json",
            "paper_readiness.md",
        ],
    }