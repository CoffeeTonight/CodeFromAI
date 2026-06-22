"""Golden case library — capture PASS verdicts and replay before promote."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

GOLDEN_REPORT = "golden_report.json"


def golden_dir(project_dir: Path, tag: str = "") -> Path:
    base = project_dir / "trust" / "golden"
    if not tag:
        cache = load_yaml(project_dir / "cache.yaml")
        tag = str((cache.get("tag") or {}).get("value") or "unknown")
    return base / tag


def verdict_fingerprint(verdict: dict[str, Any]) -> str:
    core = {
        "status": verdict.get("status"),
        "gate": verdict.get("gate"),
        "log_scan": (verdict.get("log_scan") or {}).get("ok"),
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def capture_from_verdict(
    project_dir: Path,
    *,
    stage: str,
    group: str,
    tag: str,
    verdict: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    if verdict.get("status") != "PASS":
        return {"captured": False, "reason": "not_pass"}

    fp = verdict_fingerprint(verdict)
    gdir = golden_dir(project_dir, tag)
    gdir.mkdir(parents=True, exist_ok=True)
    case_name = f"{stage}__{group}__{fp}.json"
    case_path = gdir / case_name
    if case_path.is_file():
        return {"captured": False, "reason": "duplicate", "path": str(case_path)}

    case = {
        "contract": "golden_case_v1",
        "stage": stage,
        "group": group,
        "tag": tag,
        "status": "PASS",
        "log_markers": list(verdict.get("evidence") or [])[:5],
        "exit_code": verdict.get("exit_code", 0),
        "fingerprint": fp,
        "source_run_id": run_id,
    }
    case_path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"captured": True, "path": str(case_path), "fingerprint": fp}


def run_golden_suite(
    project_dir: Path,
    script_path: Path,
    *,
    tag: str = "",
) -> dict[str, Any]:
    gdir = golden_dir(project_dir, tag)
    if not gdir.is_dir() or not any(gdir.glob("*.json")):
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_golden_cases",
            "total": 0,
            "mismatches": [],
            "contract": "golden_report_v1",
        }

    mismatches: list[dict[str, Any]] = []
    total = 0
    for case in sorted(gdir.glob("*.json")):
        total += 1
        expected = json.loads(case.read_text(encoding="utf-8"))
        proc = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--project",
                str(project_dir),
                "--case",
                str(case),
            ],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        try:
            actual = json.loads(proc.stdout)
        except json.JSONDecodeError:
            actual = {"status": "FAIL"}
        if actual.get("status") != expected.get("status"):
            mismatches.append(
                {
                    "case": case.name,
                    "expected": expected.get("status"),
                    "actual": actual.get("status"),
                }
            )

    ok = not mismatches
    return {
        "ok": ok,
        "skipped": False,
        "total": total,
        "mismatches": mismatches,
        "contract": "golden_report_v1",
    }


def write_golden_report(run_dir: Path, report: dict[str, Any]) -> Path:
    path = run_dir / GOLDEN_REPORT
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_golden_report(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / GOLDEN_REPORT
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def golden_allows_promote(run_dir: Path) -> tuple[bool, str]:
    report = load_golden_report(run_dir)
    if report is None:
        return True, "no_golden_report"
    if report.get("skipped"):
        return True, "golden_skipped"
    if not report.get("ok"):
        return False, "golden_fail"
    return True, "golden_ok"