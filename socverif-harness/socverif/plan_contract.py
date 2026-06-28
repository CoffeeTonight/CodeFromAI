"""Mechanical sync check: goal/plan.md unittest literals vs baseline.json."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from socverif.baseline import load_baseline
from socverif.constants import GOAL_BUILD_ID

DEFAULT_PLAN = Path(
    "/home/user/.grok/sessions/%2Fhome%2Fuser/"
    "019f0539-43e8-76f0-a3ec-b6a269d83593/goal/plan.md"
)

UNITTEST_EQ = re.compile(r"unittest\s*=\s*(\d+)", re.I)
UNITTEST_RAN = re.compile(r"ran\s*>=\s*(\d+)", re.I)
RAN_N_TESTS = re.compile(r"Ran\s+(\d+)\s+tests", re.I)
MIN_UNIT_TESTS = re.compile(r"min_unit_tests\s*==\s*(\d+)", re.I)
ARTIFACT_ARROW = re.compile(r"\d+\s*→\s*\d+\.?")
MANGLED_AC_LABEL = re.compile(r"^(\d+)\s+(\d+)\.\s")
AC_LINE = re.compile(r"^(\d+)\.\s")


def resolve_plan_path() -> Path | None:
    raw = os.environ.get("SOCVERIF_GOAL_PLAN", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_file() else None
    return DEFAULT_PLAN if DEFAULT_PLAN.is_file() else None


def scan_plan_literals(text: str) -> list[dict]:
    hits: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, kind in (
            (UNITTEST_EQ, "unittest="),
            (UNITTEST_RAN, "ran>="),
            (RAN_N_TESTS, "Ran N tests"),
            (MIN_UNIT_TESTS, "min_unit_tests=="),
        ):
            for m in pattern.finditer(line):
                hits.append({
                    "line": lineno,
                    "kind": kind,
                    "value": int(m.group(1)),
                    "text": line.strip()[:120],
                })
    return hits


def scan_acceptance_numbers(text: str) -> list[int]:
    """Ordered acceptance-criteria indices under ## Acceptance criteria."""
    numbers: list[int] = []
    in_acceptance = False
    for line in text.splitlines():
        if line.startswith("## Acceptance criteria"):
            in_acceptance = True
            continue
        if in_acceptance and line.startswith("## "):
            break
        if in_acceptance:
            m = AC_LINE.match(line.strip())
            if m:
                numbers.append(int(m.group(1)))
    return numbers


def scan_plan_defects(text: str, minimum: int) -> list[dict]:
    """Non-unittest plan defects: numbering artifacts, stale literals."""
    defects: list[dict] = []
    in_acceptance = False
    ac_numbers: list[int] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## Acceptance criteria"):
            in_acceptance = True
            continue
        if in_acceptance and line.startswith("## "):
            in_acceptance = False
        if re.match(r"^\s*\d+→\d+", line) or (
            in_acceptance and ARTIFACT_ARROW.search(line)
        ):
            defects.append({
                "line": lineno,
                "kind": "artifact_arrow",
                "text": line.strip()[:120],
            })
        if in_acceptance:
            mangled = MANGLED_AC_LABEL.match(line.strip())
            if mangled:
                defects.append({
                    "line": lineno,
                    "kind": "mangled_ac_label",
                    "left": int(mangled.group(1)),
                    "right": int(mangled.group(2)),
                    "text": line.strip()[:120],
                })
            m = AC_LINE.match(line.strip())
            if m:
                ac_numbers.append(int(m.group(1)))
        for stale in (94, 100, 109, 116, 121, 122, 123, 125, 126):
            if stale != minimum and re.search(rf"unittest\s*=\s*{stale}\b", line, re.I):
                defects.append({
                    "line": lineno,
                    "kind": "stale_unittest",
                    "value": stale,
                    "text": line.strip()[:120],
                })
    if ac_numbers and ac_numbers != list(range(1, max(ac_numbers) + 1)):
        defects.append({
            "kind": "acceptance_numbering_gap",
            "found": ac_numbers,
            "expected": list(range(1, len(ac_numbers) + 1)),
        })
    if ac_numbers and max(ac_numbers) != len(ac_numbers):
        defects.append({
            "kind": "acceptance_count_mismatch",
            "found": ac_numbers,
            "count": len(ac_numbers),
            "max": max(ac_numbers),
        })
    return defects


def check_plan_contract(plan_path: Path | None = None) -> dict:
    plan = plan_path or resolve_plan_path()
    minimum = int(load_baseline()["min_unit_tests"])
    if not plan or not plan.is_file():
        return {
            "goal_build_id": GOAL_BUILD_ID,
            "ok": False,
            "error": "plan.md not found",
            "minimum": minimum,
            "plan_path": str(plan) if plan else None,
        }
    text = plan.read_text(encoding="utf-8")
    hits = scan_plan_literals(text)
    mismatches = [h for h in hits if h["value"] != minimum]
    defects = scan_plan_defects(text, minimum)
    ok = not mismatches and not defects
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": ok,
        "minimum": minimum,
        "plan_path": str(plan),
        "literals_found": len(hits),
        "mismatches": mismatches,
        "defects": defects,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="plan.md unittest literal contract")
    parser.add_argument("--plan", type=Path, help="override plan.md path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check_plan_contract(args.plan)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())