"""Optional verifclaw interop — core harness works without it."""
# goal_build_id = 12

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def find_verifclaw_root(start: Path) -> Path | None:
    for candidate in [start, start.parent, start.parent.parent]:
        vc = candidate / "verifclaw"
        if (vc / "core" / "graph.py").exists():
            return vc.resolve()
        alt = candidate / "tools" / "CodeFromAI" / "verifclaw"
        if (alt / "core" / "graph.py").exists():
            return alt.resolve()
    return None


def verifclaw_available(root: Path) -> bool:
    return find_verifclaw_root(root) is not None


def analyze_report(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Hand off tier results to verifclaw memory if available; else noop summary."""
    vc_root = find_verifclaw_root(root)
    analysis = {
        "verifclaw_present": vc_root is not None,
        "summary": _local_summary(report),
        "recommendations": _local_recommendations(report),
    }
    if not vc_root:
        return analysis

    try:
        if str(vc_root) not in sys.path:
            sys.path.insert(0, str(vc_root))
        from memory.kg_memory import VerifClawMemory  # type: ignore

        mem = VerifClawMemory(db_path=str(vc_root / "verifclaw_memory.json"))
        episode = json.dumps({"harness_report": report, "summary": analysis["summary"]}, indent=0)
        mem.add_episode(episode, name=f"harness_{report.get('project_id', 'unknown')}", source_desc="socverif")
        analysis["kg_episode_stored"] = True
    except Exception as exc:  # pragma: no cover - optional path
        analysis["kg_episode_stored"] = False
        analysis["kg_error"] = str(exc)
    return analysis


def _local_summary(report: dict[str, Any]) -> str:
    results = report.get("results", [])
    if not results:
        return "no tier results"
    passed = [r for r in results if r.get("passed")]
    failed = [r for r in results if not r.get("passed")]
    if failed:
        f = failed[0]
        return f"stopped at tier {f.get('tier')} ({f.get('name')}): {f.get('errors', [])}"
    return f"all {len(passed)} tiers passed"


def _local_recommendations(report: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    for r in report.get("results", []):
        if r.get("passed"):
            continue
        errs = r.get("errors", [])
        if any("compile" in e for e in errs):
            recs.append("fix compile/filelist before advancing tiers")
        if any("VLP" in e for e in errs):
            recs.append("instrument FW with VLP self-log or add pass_fail log_pattern")
        if any("pass patterns" in e for e in errs):
            recs.append("verify sim produces expected PASS markers in log")
    return recs or ["re-run discover after environment changes"]