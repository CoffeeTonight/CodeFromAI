"""Agent bootcamp: analyze large env → fastest toy → catch errors → transfer."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.agent_transfer import (
    PREFLIGHT_GATE,
    PREFLIGHT_STAGE,
    apply_transfer_plan,
    build_transfer_plan,
    write_bootcamp_markdown,
)
from soc_verify.env_analyze import analyze_verification_env, write_analyze_report
from soc_verify.loop_lap import run_training_lap
from soc_verify.toy_intake import resolve_toy_intake, slug_toy_project_id
from soc_verify.toy_scaffold import scaffold_toy_project

# Minimal TAT bootcamp: one happy path + env + verif routing (no extra pass mid-loop).
BOOTCAMP_SCENARIOS = ("pass", "env_fail", "verif_fail", "pass")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run_agent_bootcamp(
    root: Path,
    *,
    source_project: str,
    toy_project_id: str = "",
    overwrite: bool = True,
    apply: bool = False,
    skip_toy_laps: bool = False,
    max_ticks: int = 25,
    profile: str = "training",
) -> dict[str, Any]:
    """
    Full agent loop:
      1. Analyze production verification environment
      2. Scaffold fastest-TAT toy (OSS smoke, no heavy compile)
      3. Run bootcamp scenarios (routing + happy path)
      4. Build transfer plan → production
      5. Optionally apply low-risk patches (preflight gate, env notes, clone align)
    """
    root = root.resolve()
    t0 = time.monotonic()
    source_project = source_project.strip()
    if not source_project:
        raise ValueError("source_project required")

    # --- 1. Analyze ---
    analysis = analyze_verification_env(root, source_project)
    if not analysis.get("toy_ready"):
        # Still scaffold if we can resolve intake; else fail early with analysis
        try:
            resolve_toy_intake(root, source_id=source_project)
        except (FileNotFoundError, ValueError) as exc:
            return {
                "ok": False,
                "phase": "analyze",
                "error": str(exc),
                "analysis": analysis,
                "elapsed_s": round(time.monotonic() - t0, 3),
            }

    # --- 2. Fastest toy ---
    spec = resolve_toy_intake(root, source_id=source_project)
    # Force lightest gate name for TAT
    spec.gate = "oss_smoke"
    spec.stage = "sanity"
    toy_id = slug_toy_project_id(source_project, toy_project_id)
    scaffold = scaffold_toy_project(root, spec, project_id=toy_id, overwrite=overwrite)

    # --- 3. Toy bootcamp laps ---
    laps: list[dict[str, Any]] = []
    if not skip_toy_laps:
        for i, scenario in enumerate(BOOTCAMP_SCENARIOS, 1):
            lap = run_training_lap(
                root,
                project_id=toy_id,
                stage=spec.stage,
                group=spec.gate,
                profile=profile,
                scenario=scenario,
                max_ticks=max_ticks,
            )
            m = lap.get("loop_metrics") or {}
            laps.append(
                {
                    "step": i,
                    "scenario": scenario,
                    "ok": lap.get("ok"),
                    "verdict": m.get("verdict"),
                    "ticks": m.get("tick_count"),
                    "elapsed_s": m.get("elapsed_s"),
                    "run_id": m.get("run_id"),
                    "blocked_reason": m.get("blocked_reason"),
                    "weakness_count": m.get("weakness_count"),
                }
            )

    toy_ok = bool(laps) and all(
        (lap.get("scenario") == "pass" and lap.get("verdict") == "PASS" and lap.get("ok"))
        or (lap.get("scenario") == "env_fail" and lap.get("verdict") == "BLOCKED")
        or (lap.get("scenario") == "verif_fail" and lap.get("verdict") == "FAIL")
        for lap in laps
    )
    if skip_toy_laps:
        toy_ok = True

    toy_result = {
        "ok": toy_ok,
        "project_id": toy_id,
        "stage": spec.stage,
        "group": spec.gate,
        "laps": laps,
        "scaffold": scaffold,
    }

    # --- 4. Transfer plan ---
    plan = build_transfer_plan(
        analysis=analysis,
        toy_result=toy_result,
        target_project_id=source_project,
        toy_project_id=toy_id,
    )
    transfer = apply_transfer_plan(root, plan, apply=apply, analysis=analysis)

    # Optional: run production preflight lap if applied and toy_ok
    production_preflight: dict[str, Any] | None = None
    if apply and toy_ok:
        prod_pre = root / "projects" / source_project / "ops" / PREFLIGHT_STAGE / f"{PREFLIGHT_GATE}.py"
        if prod_pre.is_file():
            pre_lap = run_training_lap(
                root,
                project_id=source_project,
                stage=PREFLIGHT_STAGE,
                group=PREFLIGHT_GATE,
                profile=profile,
                scenario="pass",
                max_ticks=max_ticks,
            )
            pm = pre_lap.get("loop_metrics") or {}
            production_preflight = {
                "ok": pre_lap.get("ok"),
                "verdict": pm.get("verdict"),
                "ticks": pm.get("tick_count"),
                "elapsed_s": pm.get("elapsed_s"),
                "run_id": pm.get("run_id"),
            }

    elapsed = round(time.monotonic() - t0, 3)
    report = {
        "contract": "agent_bootcamp_v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "source_project": source_project,
        "toy_project": toy_id,
        "ok": bool(toy_ok and (production_preflight is None or production_preflight.get("ok"))),
        "elapsed_s": elapsed,
        "analysis": analysis,
        "toy": toy_result,
        "transfer_plan": plan,
        "transfer": transfer,
        "production_preflight": production_preflight,
        "mission": {
            "goal": "fastest TAT toy → catch env/script errors → apply to large env",
            "production_next": (plan.get("actions") or [{}])[-1].get("commands") or [],
        },
    }

    # Persist under both toy and source
    session_dir = root / "projects" / toy_id / "runs" / "agent_bootcamp"
    session_dir.mkdir(parents=True, exist_ok=True)
    write_analyze_report(session_dir / "env_analyze.json", analysis)
    _write_json(session_dir / "bootcamp_report.json", report)
    write_bootcamp_markdown(session_dir / "BOOTCAMP.md", report)

    src_report = root / "projects" / source_project / "reports" / "agent_bootcamp"
    src_report.mkdir(parents=True, exist_ok=True)
    _write_json(src_report / "latest.json", report)
    write_bootcamp_markdown(src_report / "BOOTCAMP.md", report)

    return report


def run_agent_analyze(root: Path, source_project: str) -> dict[str, Any]:
    report = analyze_verification_env(root, source_project)
    out = root / "projects" / source_project / "reports" / "agent_bootcamp" / "env_analyze.json"
    write_analyze_report(out, report)
    report["report_path"] = str(out)
    return report
