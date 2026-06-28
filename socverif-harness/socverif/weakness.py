"""Weakness mining — structured failure hints for self-harness improvement loop."""
# goal_build_id = 12

from __future__ import annotations

import re
from typing import Any

from socverif.runner import TierResult


_SUGGESTIONS: list[tuple[str, str, str]] = [
    (r"sim failed rc=-1|\[TIMEOUT\]", "timeout", "Increase tier timeout_sec or reduce env matrix scope"),
    (r"sim failed rc=", "nonzero_exit", "Check sim_cmd exit code; run tier command manually"),
    (r"fail patterns matched", "log_fail_pattern", "Inspect log_tail for FATAL/UVM errors"),
    (r"required pass patterns not found", "missing_pass_pattern", "Verify pass_patterns match actual log output"),
    (r"VLP check failed", "vlp_fail", "Check VERIF SUMMARY lines in simulation log"),
    (r"compile failed", "compile_fail", "Fix compile_cmd or EDA tool availability"),
    (r"unit test count", "test_regression", "Add/fix unit tests; update baseline min_unit_tests if intentional"),
]


def mine_weaknesses(
    results: list[TierResult],
    project_id: str = "",
) -> list[dict[str, Any]]:
    """Extract failure patterns and harness improvement hints from tier results."""
    weaknesses: list[dict[str, Any]] = []
    for r in results:
        if r.passed:
            continue
        blob = " ".join(r.errors) + " " + (r.log_tail or "")
        hints: list[str] = []
        for pat, kind, suggestion in _SUGGESTIONS:
            if re.search(pat, blob, re.I):
                hints.append(suggestion)
        weaknesses.append({
            "tier": r.tier,
            "name": r.name,
            "protocol": r.protocol,
            "sim_rc": r.sim_rc,
            "errors": list(r.errors),
            "log_excerpt": (r.log_tail or "")[-1200:],
            "suggestions": hints or ["Review log_excerpt and tier sim_cmd in .socverif/manifest.yaml"],
            "kind": _classify_kind(blob),
        })
    if weaknesses and project_id:
        weaknesses[0].setdefault("project_id", project_id)
    return weaknesses


def _classify_kind(blob: str) -> str:
    for pat, kind, _ in _SUGGESTIONS:
        if re.search(pat, blob, re.I):
            return kind
    return "unknown_failure"