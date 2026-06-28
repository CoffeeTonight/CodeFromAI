"""ERL — Experiential Reflective Learning heuristics for SoC verify runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ops.self_harness import load_weakness_report, update_patterns_index


def _heuristic_title(stage: str, group: str, error_kind: str) -> str:
    parts = [p for p in (stage, group, error_kind) if p]
    return " / ".join(parts) if parts else "verify run"


def _when_clause(signals: dict[str, Any], weakness: dict[str, Any] | None) -> str:
    verdict = str(signals.get("verdict") or "UNKNOWN")
    error_kind = str(signals.get("error_kind") or "none")
    if weakness:
        return (
            f"{weakness.get('category')}: {weakness.get('summary')} "
            f"(verdict={verdict}, error_kind={error_kind})"
        )
    return f"verdict={verdict}, error_kind={error_kind}"


def _try_clause(weakness: dict[str, Any] | None, *, stage: str, group: str) -> str:
    if not weakness:
        return "Re-read CHECK.md and RESPOND.md before retry; confirm intake firmware/sim fields."
    cat = str(weakness.get("category", ""))
    hints = {
        "env_loop": "Run diagnose_env → patch_bridge; confirm license paths before run_gate.",
        "tool_artifact": "Inspect sub_stop.json; fix script/syntax; ensure verdict JSON contract.",
        "info_gap": "Stop and ask user for firmware C paths and simulation env — do not guess.",
        "stalemate_spin": "Review loop_guard signature; consider force_mode llm_full after cap.",
        "stalemate_oscillation": "Enter validation autonomy (parse_validation_items) not finalize.",
        "validation_stall": "Align CHECK tier markers with log; verify excluded_items not masking fails.",
        "parity_block": "Re-run parity_check; sync ops/{stage}/{group}.py with LLM path.",
        "llm_inefficiency": "Raise trust threshold for python runner when golden exists.",
    }
    return hints.get(cat, f"Address {cat} for {stage}/{group}.")


def _avoid_clause(weakness: dict[str, Any] | None) -> str:
    if not weakness:
        return "Do not skip graph tick after LLM without fresh verdict/sub_stop artifact."
    cat = str(weakness.get("category", ""))
    avoid = {
        "info_gap": "Do not copy example firmware paths without user_provided=true in intake.",
        "env_loop": "Do not retry run_gate without bridge patch or env profile update.",
        "tool_artifact": "Do not claim PASS without verdict_{group}.json on disk.",
        "promote_block": "Do not write reproduction scripts before promote_outcome.promoted=true.",
    }
    return avoid.get(cat, "Do not repeat the same gate command without reading new graph_step.")


def build_heuristic_markdown(
    *,
    project_id: str,
    run_id: str,
    stage: str,
    group: str,
    signals: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
    weakness_report: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    error_kind = str(signals.get("error_kind") or (snapshot or {}).get("error_kind") or "none")
    weaknesses = list((weakness_report or {}).get("weaknesses") or [])
    primary = weaknesses[0] if weaknesses else None

    tags = [
        f"#project/{project_id}",
        f"#stage/{stage}" if stage else "",
        f"#group/{group}" if group else "",
        f"#error_kind/{error_kind}" if error_kind else "",
    ]
    tags = [t for t in tags if t]

    title = _heuristic_title(stage, group, error_kind)
    lines = [
        f"# Heuristic — {title} — {run_id}",
        "",
        f"tags: {' '.join(tags)}",
        f"created: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## When",
        _when_clause(signals, primary if isinstance(primary, dict) else None),
        "",
        "## Try",
        _try_clause(primary if isinstance(primary, dict) else None, stage=stage, group=group),
        "",
        "## Avoid",
        _avoid_clause(primary if isinstance(primary, dict) else None),
        "",
        "## Evidence",
        f"- runs/{run_id}/improvement_signal.json",
        f"- runs/{run_id}/weakness_report.json",
    ]
    if (snapshot or {}).get("improvement_index") is not None:
        lines.append(f"- improvement_index: {snapshot.get('improvement_index')}")
    return "\n".join(lines) + "\n", tags


def reflect_from_run_dir(project_dir: Path, run_dir: Path, group: str = "") -> Path | None:
    """Finalize hook — write ERL heuristic when run artifacts indicate learning value."""
    signals_path = run_dir / "improvement_signal.json"
    if not signals_path.is_file():
        return None
    try:
        import json

        signals = json.loads(signals_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(signals, dict):
        return None
    if group and not signals.get("group"):
        signals["group"] = group
    return write_erl_heuristic(
        project_dir,
        run_dir,
        signals=signals,
        weakness_report=load_weakness_report(run_dir),
    )


def write_erl_heuristic(
    project_dir: Path,
    run_dir: Path,
    *,
    signals: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
    weakness_report: dict[str, Any] | None = None,
) -> Path | None:
    verdict = str(signals.get("verdict") or "")
    report = weakness_report or load_weakness_report(run_dir)
    if verdict == "PASS" and not (report or {}).get("weaknesses"):
        return None

    stage = str(signals.get("stage") or (snapshot or {}).get("stage") or "")
    group = str(signals.get("group") or (snapshot or {}).get("group") or "")

    body, tags = build_heuristic_markdown(
        project_id=project_dir.name,
        run_id=run_dir.name,
        stage=stage,
        group=group,
        signals=signals,
        snapshot=snapshot,
        weakness_report=report,
    )
    patterns_dir = project_dir / "knowledge" / "patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    path = patterns_dir / f"{run_dir.name}.md"
    path.write_text(body, encoding="utf-8")

    title = _heuristic_title(stage, group, str(signals.get("error_kind") or ""))
    update_patterns_index(project_dir, run_id=run_dir.name, tags=tags, title=title)
    return path