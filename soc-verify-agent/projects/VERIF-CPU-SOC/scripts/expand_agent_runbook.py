#!/usr/bin/env python3
"""Expand agent_runbook placeholders from cache.yaml + intake."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOC_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from ops.intake_resolve import (  # noqa: E402
    TIER_SMOKE,
    assert_intake_tier_consistency,
    get_integration_tier,
    intake_path,
    load_customer_intake,
    project_tag,
    resolve_rtl_root,
)


def _expand(text: str, *, rtl_root: Path, project_dir: Path, tag: str, clone_path: Path) -> str:
    return (
        text.replace("{RTL_ROOT}", str(rtl_root))
        .replace("{TAG}", tag)
        .replace("{cache.clone.path}", str(clone_path))
        .replace("{PROJECT_DIR}", str(project_dir))
        .replace("{SOC_VERIFY_ROOT}", str(SOC_ROOT))
        .replace("<clone>", str(clone_path))
    )


def _replace_s1_smoke(body: str, tier: str) -> str:
    smoke = TIER_SMOKE.get(tier, TIER_SMOKE["paste"])["s1_smoke_lines"]
    lines: list[str] = []
    inserted = False
    for line in body.splitlines():
        if re.search(r"make soc-paste|make soc-integration|make chip-top-example|tier [123]:", line):
            if not inserted:
                lines.extend(smoke)
                inserted = True
            continue
        lines.append(line)
    if not inserted:
        lines.extend(smoke)
    return "\n".join(lines)


def _guard_tiers_from_line(line: str) -> set[str] | None:
    if "integration_tier:" not in line:
        return None
    m = re.search(r"integration_tier:\s*(.+)$", line)
    if not m:
        return None
    raw = m.group(1).strip()
    if "skip for" in line.lower():
        skipped = {t.strip() for t in raw.split("|")}
        return {"paste", "yaml_multi", "scale"} - skipped
    return {t.strip() for t in raw.split("|")}


def _activate_tier_guarded_block(body: str, tier: str) -> str:
    lines = body.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        guard_tiers = _guard_tiers_from_line(line)
        if guard_tiers is None:
            out.append(line)
            i += 1
            continue
        block_active = tier in guard_tiers
        out.append(line)
        i += 1
        while i < len(lines):
            inner = lines[i]
            if not inner.strip():
                out.append(inner)
                i += 1
                break
            if _guard_tiers_from_line(inner) is not None:
                break
            stripped = inner.lstrip()
            if block_active and stripped.startswith("#"):
                out.append(inner[: len(inner) - len(stripped)] + stripped[2:].lstrip())
            elif not block_active and not stripped.startswith("#"):
                out.append(inner[: len(inner) - len(stripped)] + "# " + stripped)
            else:
                out.append(inner)
            i += 1
    return "\n".join(out)


def _adjust_runbook_for_tier(body: str, tier: str, key: str) -> str:
    if key == "s1_example_regression":
        return _replace_s1_smoke(body, tier)
    if key == "s9_smoke":
        return TIER_SMOKE.get(tier, TIER_SMOKE["paste"])["s9_smoke"]
    if key in {"s3_derive_hierarchy", "s4b_integration_vh", "s5_bus_connect", "s6_chip_gen_vh"}:
        return _activate_tier_guarded_block(body, tier)
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=PROJECT_DIR)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--intake", type=Path, default=None, help="default: tag deployment customer_soc_intake.yaml")
    ap.add_argument("--json", action="store_true", help="emit expanded runbook as JSON")
    args = ap.parse_args()

    tag = args.tag or project_tag(args.project)
    intake_file = args.intake or intake_path(args.project, tag=tag)
    if not intake_file.is_file():
        print(f"ERROR: intake not found: {intake_file}", file=sys.stderr)
        return 1

    if args.intake:
        from soc_verify.models import load_yaml

        data = load_yaml(args.intake) or {}
    else:
        data = load_customer_intake(args.project, tag=tag)
    runbook = data.get("agent_runbook")
    if not isinstance(runbook, dict):
        print("ERROR: intake has no agent_runbook block", file=sys.stderr)
        return 1

    rtl_root = resolve_rtl_root(args.project, tag=tag)
    from soc_verify.models import load_yaml

    cache = load_yaml(args.project / "cache.yaml") or {}
    clone_path = Path(str((cache.get("clone") or {}).get("path") or rtl_root.parent))

    try:
        assert_intake_tier_consistency(data)
        tier = get_integration_tier(data)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    tier_skip: dict[str, set[str]] = {
        "paste": {"s3_derive_hierarchy", "s4b_integration_vh", "s5_bus_connect", "s6_chip_gen_vh"},
        "yaml_multi": {"s3_derive_hierarchy", "s5_bus_connect", "s6_chip_gen_vh"},
        "scale": set(),
    }
    skip_keys = tier_skip.get(tier, set())

    expanded = {}
    for k, v in runbook.items():
        if not isinstance(v, str) or k in skip_keys:
            continue
        body = _expand(v, rtl_root=rtl_root, project_dir=args.project, tag=tag, clone_path=clone_path)
        expanded[k] = _adjust_runbook_for_tier(body, tier, k)

    if args.json:
        print(
            json.dumps(
                {"rtl_root": str(rtl_root), "tag": tag, "integration_tier": tier, "runbook": expanded},
                indent=2,
            )
        )
    else:
        print(f"# rtl_root={rtl_root} tag={tag} integration_tier={tier}")
        for key, body in expanded.items():
            print(f"\n## {key}\n{body.rstrip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())