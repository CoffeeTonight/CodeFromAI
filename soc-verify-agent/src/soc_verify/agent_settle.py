"""Closed-loop settle: toy complete → apply production → residual → re-toy (TAT).

Mission SSOT: registry/agent_mission.yaml
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.agent_bootcamp import run_agent_bootcamp
from soc_verify.agent_transfer import PREFLIGHT_GATE, PREFLIGHT_STAGE
from soc_verify.loop_lap import run_training_lap
from soc_verify.models import load_yaml, save_yaml
from soc_verify.toy_intake import slug_toy_project_id

_PATH_RE = re.compile(
    r"(?:missing OSS artifact:\s*)?([A-Za-z0-9_./-]+\.(?:sh|hex|bin|vh|vvp|vcd|sv|v)|"
    r"(?:firmware|rtl|include|filelists|sim_build)[A-Za-z0-9_./-]*)"
)

MISSION_PATH = Path("registry/agent_mission.yaml")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_mission(root: Path) -> dict[str, Any]:
    path = root / MISSION_PATH
    if path.is_file():
        return load_yaml(path) or {}
    return {"contract": "agent_mission_v1", "purpose_ko": "(mission file missing)"}


def _load_verdict(run_dir: Path, group: str) -> dict[str, Any] | None:
    path = run_dir / f"verdict_{group}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _residual_from_production_lap(lap: dict[str, Any], *, group: str) -> list[dict[str, Any]]:
    """Extract residuals the toy must learn from production probe failure."""
    m = lap.get("loop_metrics") or {}
    residuals: list[dict[str, Any]] = []
    if m.get("verdict") == "PASS" and lap.get("ok"):
        return residuals

    run_id = str(m.get("run_id") or "")
    residuals.append(
        {
            "kind": "production_probe",
            "severity": "high" if m.get("verdict") in ("FAIL", "BLOCKED") else "medium",
            "verdict": m.get("verdict"),
            "blocked_reason": m.get("blocked_reason"),
            "run_id": run_id,
            "group": group,
            "evidence": [
                f"production {group} verdict={m.get('verdict')}",
                f"ticks={m.get('tick_count')} elapsed={m.get('elapsed_s')}",
            ],
            "fix_to_toy": (
                "Encode this failure mode into toy required_artifacts / CHECK / scenarios "
                "so the next toy lap fails fast before production."
            ),
        }
    )
    return residuals


def reflect_residuals_into_toy(
    root: Path,
    *,
    toy_project_id: str,
    residuals: list[dict[str, Any]],
    production_project: str,
    round_idx: int,
) -> dict[str, Any]:
    """Write residual errors back into the toy project for fast TAT re-practice."""
    toy_dir = root / "projects" / toy_project_id
    if not toy_dir.is_dir():
        raise FileNotFoundError(f"toy project missing: {toy_dir}")

    lessons_dir = toy_dir / "knowledge" / "lessons"
    lessons_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lesson_path = lessons_dir / f"round{round_idx}_{stamp}.json"
    payload = {
        "contract": "toy_lesson_v1",
        "from_production": production_project,
        "round": round_idx,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "residuals": residuals,
    }
    _write_json(lesson_path, payload)

    # Append to meta/toy_gate.yaml as residual_checks (does not fail smoke until asserted)
    gate_path = toy_dir / "meta" / "toy_gate.yaml"
    gate = load_yaml(gate_path) if gate_path.is_file() else {}
    gate = gate or {}
    hist = list(gate.get("production_residuals") or [])
    for r in residuals:
        hist.append(
            {
                "round": round_idx,
                "verdict": r.get("verdict"),
                "group": r.get("group"),
                "summary": (r.get("evidence") or [""])[0],
                "lesson": str(lesson_path.relative_to(toy_dir)),
            }
        )
    gate["production_residuals"] = hist[-20:]
    notes = list(gate.get("settle_notes") or [])
    for r in residuals:
        note = f"R{round_idx}: production {r.get('group')} → {r.get('verdict')}"
        if note not in notes:
            notes.append(note)
    gate["settle_notes"] = notes[-30:]

    # Promote path-like evidence into required_artifacts so next toy smoke fails fast
    req = list(gate.get("required_artifacts") or [])
    promoted: list[str] = []
    for r in residuals:
        for ev in r.get("evidence") or []:
            for m in _PATH_RE.finditer(str(ev)):
                rel = m.group(1).lstrip("./")
                if rel and rel not in req and " " not in rel:
                    req.append(rel)
                    promoted.append(rel)
    if promoted:
        gate["required_artifacts"] = req
        gate["promoted_from_production"] = list(
            dict.fromkeys(list(gate.get("promoted_from_production") or []) + promoted)
        )[-30:]
    save_yaml(gate_path, gate)

    # Human-readable pattern for next LLM / engineer
    pattern = toy_dir / "patterns" / f"settle_round{round_idx}.md"
    pattern.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Settle lesson — round {round_idx}",
        "",
        f"from: `{production_project}` → toy `{toy_project_id}`",
        "",
        "## Residuals",
    ]
    for r in residuals:
        lines.append(f"- **{r.get('verdict')}** `{r.get('group')}`: {', '.join(r.get('evidence') or [])}")
        lines.append(f"  - fix_to_toy: {r.get('fix_to_toy')}")
    lines.append("")
    pattern.write_text("\n".join(lines), encoding="utf-8")

    return {
        "lesson_path": str(lesson_path),
        "pattern_path": str(pattern),
        "toy_gate_updated": str(gate_path),
        "residual_count": len(residuals),
        "promoted_artifacts": promoted,
    }


def run_agent_settle(
    root: Path,
    *,
    source_project: str,
    toy_project_id: str = "",
    max_rounds: int = 2,
    apply: bool = True,
    skip_initial_bootcamp_laps: bool = False,
    max_ticks: int = 25,
    profile: str = "training",
    probe_stage: str = PREFLIGHT_STAGE,
    probe_group: str = PREFLIGHT_GATE,
) -> dict[str, Any]:
    """
    Closed loop per agent_mission.yaml:

      toy complete (bootcamp) → apply → production probe
        → residual → reflect into toy → toy re-pass (TAT)
        → repeat until settled or max_rounds
    """
    root = root.resolve()
    mission = load_mission(root)
    t0 = time.monotonic()
    source_project = source_project.strip()
    toy_id = slug_toy_project_id(source_project, toy_project_id)

    rounds: list[dict[str, Any]] = []
    settled = False

    for ridx in range(1, max_rounds + 1):
        round_rec: dict[str, Any] = {"round": ridx, "phases": {}}

        # --- toy complete + apply (bootcamp) ---
        boot = run_agent_bootcamp(
            root,
            source_project=source_project,
            toy_project_id=toy_id,
            overwrite=True,
            apply=apply,
            skip_toy_laps=skip_initial_bootcamp_laps and ridx == 1,
            max_ticks=max_ticks,
            profile=profile,
        )
        round_rec["phases"]["toy_complete"] = {
            "ok": boot.get("ok"),
            "toy_laps": (boot.get("toy") or {}).get("laps"),
            "elapsed_s": boot.get("elapsed_s"),
        }
        round_rec["phases"]["apply"] = {
            "ok": bool((boot.get("transfer") or {}).get("ok", True)),
            "apply": apply,
            "results": (boot.get("transfer") or {}).get("results"),
        }

        # --- production probe ---
        probe_group_effective = probe_group
        ops_probe = root / "projects" / source_project / "ops" / probe_stage / f"{probe_group}.py"
        if not ops_probe.is_file():
            # fall back to analysis preferred gate if preflight missing
            pref = (boot.get("analysis") or {}).get("preferred_production_gate") or {}
            if pref.get("stage") and pref.get("group"):
                probe_stage = str(pref["stage"])
                probe_group_effective = str(pref["group"])

        probe_lap: dict[str, Any] | None = None
        probe_ops = (
            root / "projects" / source_project / "ops" / probe_stage / f"{probe_group_effective}.py"
        )
        if probe_ops.is_file():
            probe_lap = run_training_lap(
                root,
                project_id=source_project,
                stage=probe_stage,
                group=probe_group_effective,
                profile=profile,
                scenario="pass",
                max_ticks=max_ticks,
            )
        else:
            probe_lap = {
                "ok": False,
                "loop_metrics": {
                    "verdict": "FAIL",
                    "blocked_reason": f"missing ops {probe_stage}/{probe_group_effective}",
                },
            }

        pm = (probe_lap or {}).get("loop_metrics") or {}
        probe_ok = bool(probe_lap.get("ok") and pm.get("verdict") == "PASS")
        round_rec["phases"]["probe_production"] = {
            "ok": probe_ok,
            "stage": probe_stage,
            "group": probe_group_effective,
            "verdict": pm.get("verdict"),
            "ticks": pm.get("tick_count"),
            "elapsed_s": pm.get("elapsed_s"),
            "run_id": pm.get("run_id"),
        }

        residuals = _residual_from_production_lap(
            probe_lap or {}, group=probe_group_effective
        )
        round_rec["residuals"] = residuals

        if probe_ok and boot.get("ok"):
            settled = True
            round_rec["settled"] = True
            rounds.append(round_rec)
            break

        # --- reflect residual → toy ---
        if residuals:
            reflect = reflect_residuals_into_toy(
                root,
                toy_project_id=toy_id,
                residuals=residuals,
                production_project=source_project,
                round_idx=ridx,
            )
            round_rec["phases"]["reflect"] = reflect
        else:
            round_rec["phases"]["reflect"] = {"residual_count": 0}

        # --- re-toy pass (TAT practice after reflection) ---
        retoy = run_training_lap(
            root,
            project_id=toy_id,
            stage="sanity",
            group="oss_smoke",
            profile=profile,
            scenario="pass",
            max_ticks=max_ticks,
        )
        rm = retoy.get("loop_metrics") or {}
        round_rec["phases"]["retoy"] = {
            "ok": retoy.get("ok"),
            "verdict": rm.get("verdict"),
            "ticks": rm.get("tick_count"),
            "elapsed_s": rm.get("elapsed_s"),
            "run_id": rm.get("run_id"),
        }
        rounds.append(round_rec)

    elapsed = round(time.monotonic() - t0, 3)
    report = {
        "contract": "agent_settle_v1",
        "mission": mission.get("purpose_ko", ""),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_project": source_project,
        "toy_project": toy_id,
        "settled": settled,
        "max_rounds": max_rounds,
        "rounds_run": len(rounds),
        "elapsed_s": elapsed,
        "rounds": rounds,
        "success_criteria": (mission.get("success") or {}).get("settled_when"),
    }

    out_dir = root / "projects" / source_project / "reports" / "agent_settle"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "latest.json", report)
    md = [
        "# Agent Settle Report",
        "",
        f"- settled: **{settled}**",
        f"- source: `{source_project}` toy: `{toy_id}`",
        f"- rounds: {len(rounds)} / {max_rounds}",
        f"- elapsed_s: {elapsed}",
        "",
        "## Mission",
        "",
        (mission.get("purpose_ko") or "").strip(),
        "",
        "## Rounds",
        "",
    ]
    for rec in rounds:
        md.append(f"### Round {rec['round']}")
        for name, phase in (rec.get("phases") or {}).items():
            md.append(f"- `{name}`: {json.dumps(phase, ensure_ascii=False)[:200]}")
        if rec.get("residuals"):
            md.append(f"- residuals: {len(rec['residuals'])}")
        md.append("")
    (out_dir / "SETTLE.md").write_text("\n".join(md), encoding="utf-8")
    report["report_md"] = str(out_dir / "SETTLE.md")
    return report
