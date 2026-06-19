#!/usr/bin/env python3
"""Expand agent_runbook placeholders from cache.yaml + intake."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOC_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from ops.intake_resolve import (  # noqa: E402
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

    expanded = {
        k: _expand(v, rtl_root=rtl_root, project_dir=args.project, tag=tag, clone_path=clone_path)
        for k, v in runbook.items()
        if isinstance(v, str)
    }

    if args.json:
        print(json.dumps({"rtl_root": str(rtl_root), "tag": tag, "runbook": expanded}, indent=2))
    else:
        print(f"# rtl_root={rtl_root} tag={tag}")
        for key, body in expanded.items():
            print(f"\n## {key}\n{body.rstrip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())