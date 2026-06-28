"""Baseline regression gates for self-harness reports."""
# goal_build_id = 12

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT

BASELINE_PATH = HARNESS_ROOT / ".socverif" / "baseline.json"


def load_baseline(path: Path | None = None) -> dict[str, Any]:
    p = path or BASELINE_PATH
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def validate_self_harness_report(
    report: dict[str, Any],
    manifest_raw: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
) -> list[str]:
    """Return validation errors (empty list = pass)."""
    spec = baseline or load_baseline()
    errors: list[str] = []

    if spec.get("goal_build_id") and spec["goal_build_id"] != GOAL_BUILD_ID:
        errors.append(f"baseline goal_build_id mismatch: expect {GOAL_BUILD_ID}")

    if not report.get("all_passed"):
        errors.append("report all_passed is false")

    results = report.get("results", [])
    if spec.get("self_harness_tier_count"):
        expected = int(spec["self_harness_tier_count"])
        if manifest_raw:
            tier_count = len(manifest_raw.get("tiers", []))
            if tier_count != expected:
                errors.append(f"tier count {tier_count} != baseline {expected}")

    if spec.get("required_tier_names") and manifest_raw:
        names = [t.get("name") for t in manifest_raw.get("tiers", [])]
        for req in spec["required_tier_names"]:
            if req not in names:
                errors.append(f"missing required tier name: {req}")

    for r in results:
        dur = r.get("duration_sec")
        max_dur = (spec.get("max_tier_duration_sec") or {}).get(str(r.get("tier")))
        if dur is not None and max_dur is not None and dur > max_dur:
            errors.append(f"tier {r.get('tier')} duration {dur}s > budget {max_dur}s")

    if spec.get("discovery_tier_names"):
        ran = {r.get("name") for r in results}
        for name in spec["discovery_tier_names"]:
            if name not in ran:
                errors.append(f"baseline tier not executed: {name}")

    return errors


def validate_help_text(text: str, baseline: dict[str, Any] | None = None) -> list[str]:
    spec = baseline or load_baseline()
    errors: list[str] = []
    for sub in spec.get("required_cli_subcommands", []):
        if sub not in text:
            errors.append(f"help missing subcommand: {sub}")
    return errors


def parse_unittest_count(text: str) -> int | None:
    m = re.search(r"Ran (\d+) tests", text)
    return int(m.group(1)) if m else None


def validate_unittest_count(
    ran: int,
    baseline: dict[str, Any] | None = None,
) -> list[str]:
    """Ensure discovered test count meets baseline min_unit_tests."""
    spec = baseline or load_baseline()
    minimum = spec.get("min_unit_tests")
    if minimum is None:
        return []
    if ran < int(minimum):
        return [f"unit test count {ran} < baseline {minimum}"]
    return []