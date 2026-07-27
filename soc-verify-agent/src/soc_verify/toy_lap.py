"""Intake → toy scaffold → training lap (one-shot or zigzag)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from soc_verify.loop_lap import run_training_lap
from soc_verify.toy_intake import resolve_toy_intake, slug_toy_project_id
from soc_verify.toy_scaffold import scaffold_toy_project

ZIGZAG_SCENARIOS = ("pass", "env_fail", "pass", "verif_fail", "pass")


def run_toy_from_intake(
    root: Path,
    *,
    source_id: str = "",
    discovered_file: Path | None = None,
    project_id: str = "",
    overwrite: bool = False,
    profile: str = "training",
    scenario: str = "pass",
    zigzag: bool = False,
    max_ticks: int = 35,
) -> dict[str, Any]:
    """Resolve intake, scaffold toy project, run training lap(s)."""
    root = root.resolve()
    spec = resolve_toy_intake(root, source_id=source_id, discovered_file=discovered_file)
    pid = slug_toy_project_id(spec.source_id, project_id)

    scaffold = scaffold_toy_project(root, spec, project_id=pid, overwrite=overwrite)

    laps: list[dict[str, Any]] = []
    scenarios: tuple[str, ...] = ZIGZAG_SCENARIOS if zigzag else (scenario,)

    t0 = time.monotonic()
    for label, scen in enumerate(scenarios, 1):
        lap = run_training_lap(
            root,
            project_id=pid,
            stage=spec.stage,
            group=spec.gate,
            profile=profile,
            scenario=scen,
            max_ticks=max_ticks,
        )
        m = lap.get("loop_metrics") or {}
        laps.append(
            {
                "step": label,
                "scenario": scen,
                "ok": lap.get("ok"),
                "verdict": m.get("verdict"),
                "ticks": m.get("tick_count"),
                "elapsed_s": m.get("elapsed_s"),
                "run_id": m.get("run_id"),
                "blocked_reason": m.get("blocked_reason"),
            }
        )

    elapsed = time.monotonic() - t0
    last_lap = laps[-1] if laps else {}
    zigzag_ok = zigzag and all(
        (lap.get("verdict") == "PASS" and lap.get("scenario") == "pass")
        or (lap.get("scenario") == "env_fail" and lap.get("verdict") == "BLOCKED")
        or (lap.get("scenario") == "verif_fail" and lap.get("verdict") == "FAIL")
        for lap in laps
    )
    return {
        "ok": zigzag_ok if zigzag else bool(last_lap.get("ok")),
        "project_id": pid,
        "source_id": spec.source_id,
        "scaffold": scaffold,
        "zigzag": zigzag,
        "laps": laps,
        "elapsed_s": round(elapsed, 3),
        "stage": spec.stage,
        "group": spec.gate,
        "last_verdict": last_lap.get("verdict"),
        "last_run_id": last_lap.get("run_id"),
    }


def run_toy_scaffold_only(
    root: Path,
    *,
    source_id: str = "",
    discovered_file: Path | None = None,
    project_id: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    spec = resolve_toy_intake(root, source_id=source_id, discovered_file=discovered_file)
    pid = slug_toy_project_id(spec.source_id, project_id)
    return scaffold_toy_project(root, spec, project_id=pid, overwrite=overwrite)