#!/usr/bin/env python3
"""Align intake simulation.run/pass with chip.integration_tier (vault 13-INTEGRATION-TIERS SSOT)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from ops.intake_resolve import (  # noqa: E402
    get_integration_tier,
    intake_path,
    project_tag,
    sync_intake_simulation_to_tier,
)
import yaml

from soc_verify.models import load_yaml, save_yaml


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=PROJECT_DIR)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--intake", type=Path, default=None, help="YAML to read/write (default: tag deployment intake)")
    ap.add_argument("--dry-run", action="store_true", help="print synced YAML to stdout only")
    args = ap.parse_args()

    tag = args.tag or project_tag(args.project)
    intake_file = args.intake or intake_path(args.project, tag=tag)
    if not intake_file.is_file():
        print(f"ERROR: missing intake: {intake_file}", file=sys.stderr)
        return 1

    data = load_yaml(intake_file) or {}
    synced = sync_intake_simulation_to_tier(data)
    tier = get_integration_tier(synced)
    print(f"[sync] integration_tier={tier} simulation blocks aligned")

    if args.dry_run:
        print(yaml.safe_dump(synced, allow_unicode=True, sort_keys=False))
        return 0

    save_yaml(intake_file, synced)
    print(f"[sync] wrote {intake_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())