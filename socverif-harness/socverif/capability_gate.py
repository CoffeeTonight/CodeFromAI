"""Self-harness capability gate — toy TAT + VLP exactness after repeat streak."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT

ELAPSED_RE = re.compile(r"(?:elapsed|_elapsed)\s+([0-9.]+)", re.I)
MAX_TOY_TAT_SEC = 30.0
REQUIRED_PASSES = ("sfr_batch_rmw",)


def _read_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tier2_vlp(report: dict) -> dict:
    for row in report.get("results", []):
        if row.get("tier") == 2:
            return row.get("vlp", {})
    return {}


def _parse_elapsed_from_log(log_text: str) -> float | None:
    hits = [float(m.group(1)) for m in ELAPSED_RE.finditer(log_text)]
    return max(hits) if hits else None


def check_toy_report(
    report_path: Path,
    *,
    max_tier: int = 2,
    required_passes: tuple[str, ...] = REQUIRED_PASSES,
) -> dict:
    report = _read_report(report_path)
    vlp = _tier2_vlp(report)
    passes = list(vlp.get("passes", []))
    missing = [p for p in required_passes if p not in passes]
    vlp_result = vlp.get("result")
    if vlp_result is None and isinstance(vlp.get("summary"), dict):
        vlp_result = vlp["summary"].get("result")
    ok = (
        report.get("all_passed") is True
        and report.get("max_tier") == max_tier
        and report.get("tiers_to_run") == max_tier + 1
        and report.get("tiers_run") == report.get("tiers_to_run")
        and len(report.get("results", [])) == max_tier + 1
        and not missing
        and vlp_result == "PASS"
    )
    return {
        "report": str(report_path),
        "ok": ok,
        "tiers_run": report.get("tiers_run"),
        "vlp_passes": passes,
        "missing_passes": missing,
    }


def check_toy_loop_tat(log_path: Path, *, ceiling: float = MAX_TOY_TAT_SEC) -> dict:
    elapsed = _parse_elapsed_from_log(log_path.read_text(encoding="utf-8", errors="replace"))
    ok = elapsed is not None and elapsed <= ceiling
    return {
        "log": str(log_path),
        "elapsed_sec": elapsed,
        "ceiling_sec": ceiling,
        "ok": ok,
    }


def run_toy_capability_probe(
    env_rel: str = "envs/toy_mimic_soc",
    *,
    max_tier: int = 2,
    ceiling: float = MAX_TOY_TAT_SEC,
) -> dict:
    env = HARNESS_ROOT / env_rel
    log_path = env / "sim_logs" / "tier2.log"
    report_path = env / "verif_report.json"
    t0 = time.monotonic()
    import subprocess

    proc = subprocess.run(
        [
            sys.executable, "-m", "socverif.cli", "loop",
            str(env), "--max-tier", str(max_tier),
        ],
        cwd=HARNESS_ROOT,
        capture_output=True,
        text=True,
    )
    wall = time.monotonic() - t0
    report_check = check_toy_report(report_path, max_tier=max_tier)
    tat_check = {
        "wall_sec": round(wall, 3),
        "ceiling_sec": ceiling,
        "ok": wall <= ceiling,
    }
    ok = proc.returncode == 0 and report_check["ok"] and tat_check["ok"]
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": ok,
        "rc": proc.returncode,
        "report_check": report_check,
        "tat_check": tat_check,
        "stdout_tail": proc.stdout.splitlines()[-5:] if proc.stdout else [],
    }


@dataclass
class CapabilityAcquireConfig:
    required_streak: int = 3
    max_rounds: int = 7
    max_tier: int = 2
    toy_loop_repeat: int = 3
    tat_ceiling_sec: float = MAX_TOY_TAT_SEC


@dataclass
class CapabilityAcquireResult:
    ok: bool
    streak: int
    rounds: int
    probe: dict
    toy_create: dict
    checklist: list[dict]
    message: str


def evaluate_acquire_checklist(
    *,
    streak: int,
    required_streak: int,
    probe: dict,
    toy_create_report: dict | None,
    toy_create_log_has_sfr: bool,
) -> list[dict]:
    tier2 = {}
    if toy_create_report:
        for row in toy_create_report.get("results", []):
            if row.get("tier") == 2:
                tier2 = row.get("vlp", {})
    items = [
        {
            "id": "streak",
            "ok": streak >= required_streak,
            "detail": f"streak={streak} required>={required_streak}",
        },
        {
            "id": "probe_toy",
            "ok": bool(probe.get("ok")),
            "detail": probe,
        },
        {
            "id": "toy_create_sfr_log",
            "ok": toy_create_log_has_sfr,
            "detail": "sfr_batch_rmw in tier2.log",
        },
        {
            "id": "toy_create_vlp",
            "ok": "sfr_batch_rmw" in tier2.get("passes", []),
            "detail": tier2.get("passes", []),
        },
    ]
    return items


def summarize_acquire(
    *,
    streak: int,
    rounds: int,
    config: CapabilityAcquireConfig,
    probe: dict,
    toy_create_report: dict | None,
    toy_create_log_has_sfr: bool,
) -> CapabilityAcquireResult:
    checklist = evaluate_acquire_checklist(
        streak=streak,
        required_streak=config.required_streak,
        probe=probe,
        toy_create_report=toy_create_report,
        toy_create_log_has_sfr=toy_create_log_has_sfr,
    )
    ok = all(item["ok"] for item in checklist)
    msg = (
        f"SELF_HARNESS_CAPABILITY_ACQUIRED streak={streak} toy_repeat={config.toy_loop_repeat}"
        if ok
        else "SELF_HARNESS_CAPABILITY_FAIL"
    )
    return CapabilityAcquireResult(
        ok=ok,
        streak=streak,
        rounds=rounds,
        probe=probe,
        toy_create={"report": toy_create_report, "log_has_sfr": toy_create_log_has_sfr},
        checklist=checklist,
        message=msg,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="self-harness capability gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check-report")
    p_check.add_argument("report", type=Path)
    p_check.add_argument("--max-tier", type=int, default=2)

    p_probe = sub.add_parser("probe-toy")
    p_probe.add_argument("--env", default="envs/toy_mimic_soc")
    p_probe.add_argument("--max-tier", type=int, default=2)
    p_probe.add_argument("--ceiling", type=float, default=MAX_TOY_TAT_SEC)

    p_eval = sub.add_parser("evaluate-acquire")
    p_eval.add_argument("--streak", type=int, required=True)
    p_eval.add_argument("--rounds", type=int, default=0)
    p_eval.add_argument("--probe-json", type=Path, required=True)
    p_eval.add_argument("--toy-report", type=Path)
    p_eval.add_argument("--toy-tier2-log", type=Path)
    p_eval.add_argument("--required-streak", type=int, default=3)
    p_eval.add_argument("--toy-repeat", type=int, default=3)

    args = parser.parse_args(argv)
    if args.cmd == "check-report":
        result = check_toy_report(args.report, max_tier=args.max_tier)
        ok = result["ok"]
    elif args.cmd == "evaluate-acquire":
        probe = json.loads(args.probe_json.read_text(encoding="utf-8"))
        toy_report = None
        if args.toy_report and args.toy_report.is_file():
            toy_report = json.loads(args.toy_report.read_text(encoding="utf-8"))
        log_has_sfr = False
        if args.toy_tier2_log and args.toy_tier2_log.is_file():
            log_has_sfr = "sfr_batch_rmw" in args.toy_tier2_log.read_text(encoding="utf-8", errors="replace")
        cfg = CapabilityAcquireConfig(
            required_streak=args.required_streak,
            toy_loop_repeat=args.toy_repeat,
        )
        summary = summarize_acquire(
            streak=args.streak,
            rounds=args.rounds,
            config=cfg,
            probe=probe,
            toy_create_report=toy_report,
            toy_create_log_has_sfr=log_has_sfr,
        )
        result = asdict(summary)
        ok = result["ok"]
    else:
        result = run_toy_capability_probe(args.env, max_tier=args.max_tier, ceiling=args.ceiling)
        ok = result["ok"]
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())